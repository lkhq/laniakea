# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import re
from enum import Enum, auto

from pebble import ThreadPool
from apt_pkg import version_compare
from sqlalchemy import and_, func, exists
from sqlalchemy.orm import joinedload

import laniakea.typing as T
from laniakea import LkModule, LocalConfig
from laniakea.db import (
    DebType,
    NewPolicy,
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveComponent,
    SynchrotronIssue,
    SynchrotronConfig,
    SynchrotronSource,
    SyncBlacklistEntry,
    ArchiveArchitecture,
    SynchrotronIssueKind,
    ArchiveRepoSuiteSettings,
    session_scope,
    config_get_distro_tag,
)
from laniakea.utils import process_file_lock
from laniakea.archive import (
    PackageImporter,
    ArchivePackageExistsError,
    copy_source_package,
)
from laniakea.logging import log
from laniakea.msgstream import EventEmitter
from laniakea.reporeader import (
    RepositoryReader,
    ExternalBinaryPackage,
    ExternalSourcePackage,
    version_revision,
    make_newest_packages_dict,
)
from laniakea.archive.utils import (
    package_mark_published,
    repo_suite_settings_for,
    repo_suite_settings_for_debug,
)


class PackageSyncState(Enum):
    """Synchronization state of a source package."""

    UNKNOWN = auto()
    PRESENT = auto()  # source package was already present
    COPIED = auto()  # source package was copied from within the target repo
    SYNCED = auto()  # source package was pulled into target from origin


class SyncEngine:
    """Execute package synchronization in Synchrotron"""

    def __init__(self, repo_name: T.Optional[str], target_suite_name: str, source_os_name: str, source_suite_name: str):
        self._lconf = LocalConfig()
        if not repo_name:
            repo_name = self._lconf.master_repo_name
        self._repo_name = repo_name

        # the repository of the distribution we import stuff into
        self._target_suite_name = target_suite_name
        self._source_suite_name = source_suite_name
        self._source_os_name = source_os_name
        self._distro_tag = config_get_distro_tag()
        self._synced_source_pkgs: list[T.Tuple[ExternalSourcePackage, PackageSyncState]] = []

        if not self._distro_tag:
            log.warning('No distribution tag is set! We may override any manual uploads.')
            self._distro_tag = '__unset'

        self._ev_emitter = EventEmitter(LkModule.SYNCHROTRON)

        with session_scope() as session:
            sync_source = self._get_sync_source(session)

            # the repository of the distribution we use to sync stuff from
            self._source_reader = RepositoryReader(
                sync_source.repo_url, sync_source.os_name, self._lconf.synchrotron_sourcekeyrings
            )

            self._sync_blacklist = set(
                [
                    value
                    for value, in session.query(SyncBlacklistEntry.pkgname)
                    .filter(SyncBlacklistEntry.config_id == sync_source.id)
                    .all()
                ]
            )

        # we trust everything by default
        self._imports_trusted = True

    def _get_sync_source(self, session) -> SynchrotronSource:
        sync_source = (
            session.query(SynchrotronSource)
            .filter(
                SynchrotronSource.os_name == self._source_os_name,
                SynchrotronSource.suite_name == self._source_suite_name,
            )
            .one_or_none()
        )
        if not sync_source:
            raise Exception(
                'Synchronization package source {}/{} was not found in registry.'.format(
                    self._source_os_name, self._source_suite_name
                )
            )

        return sync_source

    def _publish_synced_spkg_events(self, src_os, src_suite, dest_suite, forced=False):
        '''Submit events for the synced source packages to the message stream'''

        for spkg, _ in self._synced_source_pkgs:
            data = {
                'name': spkg.name,
                'version': spkg.version,
                'src_os': src_os,
                'suite_src': src_suite,
                'suite_dest': dest_suite,
                'forced': forced,
            }

            self._ev_emitter.submit_event('src-package-imported', data)

    def _get_source_repo_binary_package_map(
        self, suite_name: str, component_name: str, arch_name: str = None, with_installer: bool = True
    ) -> dict[str, ExternalBinaryPackage]:
        '''Get an associative array of the newest binary packages present in a repository.'''

        log.debug('Retrieving binary package map for source suite: %s/%s/%s', suite_name, component_name, arch_name)
        suite = ArchiveSuite(suite_name)
        component = ArchiveComponent(component_name)
        arch = ArchiveArchitecture(arch_name)
        arch_all = ArchiveArchitecture('all')
        bpkgs = self._source_reader.binary_packages(suite, component, arch)
        bpkgs.extend(self._source_reader.binary_packages(suite, component, arch_all))  # always append arch:all packages

        if with_installer:
            # add d-i packages to the mix
            bpkgs.extend(self._source_reader.installer_packages(suite, component, arch))
            bpkgs.extend(
                self._source_reader.installer_packages(suite, component, arch_all)
            )  # always append arch:all packages
        return make_newest_packages_dict(bpkgs)

    def _get_source_repo_source_packages(self, suite_name: str, component_name: str) -> list[ExternalSourcePackage]:
        """Get a list of all source packages present in the source repository."""

        log.debug('Retrieving source packages for source suite: %s/%s', suite_name, component_name)
        suite = ArchiveSuite(suite_name)
        component = ArchiveComponent(component_name)
        return self._source_reader.source_packages(suite, component)

    def _get_source_repo_source_package_map(self, suite_name: str, component_name: str):
        """Get an associative array of the newest source packages present in the source repository."""

        spkgs = self._get_source_repo_source_packages(suite_name, component_name)
        log.debug('Retrieving source package map for source suite: %s/%s', suite_name, component_name)
        return make_newest_packages_dict(spkgs)

    def _get_target_source_package_map(self, session, component_name: str, *, suite_name: T.Optional[str] = None):
        """Get mapping of all sources packages in a suite and its parent suite."""

        if not suite_name:
            suite_name = self._target_suite_name

        log.debug('Retrieving source package map for destination suite: %s', suite_name)
        target_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one()
        spkg_filters = [
            SourcePackage.repo.has(name=self._repo_name),
            SourcePackage.suites.any(id=target_suite.id),
            SourcePackage.component.has(name=component_name),
            SourcePackage.time_deleted.is_(None),
        ]

        spkg_filter_sq = session.query(SourcePackage).filter(*spkg_filters).subquery()
        smv_sq = (
            session.query(spkg_filter_sq.c.name, func.max(spkg_filter_sq.c.version).label('max_version'))
            .group_by(spkg_filter_sq.c.name)
            .subquery('smv_sq')
        )

        # get the latest source packages for this configuration
        spkgs = (
            session.query(SourcePackage)
            .options(joinedload(SourcePackage.binaries))
            .filter(*spkg_filters)
            .join(
                smv_sq,
                and_(
                    SourcePackage.name == smv_sq.c.name,
                    SourcePackage.version == smv_sq.c.max_version,
                ),
            )
            .order_by(SourcePackage.name)
            .all()
        )

        spkg_map = {}
        for p in spkgs:
            spkg_map[p.name] = p

        for parent in target_suite.parents:
            # we have a parent suite
            parent_map = self._get_target_source_package_map(session, component_name, suite_name=parent.name)
            # merge the two arrays, keeping only the latest versions
            # FIXME: This can be very slow, we can likely just do a better SQL query here instead of doing this in Python
            spkg_map = make_newest_packages_dict(list(parent_map.values()) + list(spkg_map.values()))

        return spkg_map

    def _get_target_binary_packages(
        self,
        session,
        rss: ArchiveRepoSuiteSettings,
        component_name: str,
        arch_name: str = None,
        *,
        deb_type=DebType.DEB,
    ):
        log.debug(
            'Retrieving binary packages for destination suite: %s:%s/%s/%s (%s)',
            rss.repo.name,
            rss.suite.name,
            component_name,
            arch_name,
            'udeb' if deb_type == DebType.UDEB else 'deb',
        )
        bpkg_filter = [
            BinaryPackage.deb_type == deb_type,
            BinaryPackage.repo.has(id=rss.repo_id),
            BinaryPackage.suites.any(id=rss.suite_id),
            BinaryPackage.component.has(name=component_name),
            BinaryPackage.architecture.has(name=arch_name),
            BinaryPackage.time_deleted.is_(None),
        ]

        bpkg_filter_sq = session.query(BinaryPackage).filter(*bpkg_filter).subquery()
        bmv_sq = (
            session.query(bpkg_filter_sq.c.name, func.max(bpkg_filter_sq.c.version).label('max_version'))
            .group_by(bpkg_filter_sq.c.name)
            .subquery('bmv_sq')
        )

        # get the latest binary packages for this configuration
        bpkgs = (
            session.query(BinaryPackage)
            .filter(*bpkg_filter)
            .join(
                bmv_sq,
                and_(
                    BinaryPackage.name == bmv_sq.c.name,
                    BinaryPackage.version == bmv_sq.c.max_version,
                ),
            )
            .order_by(BinaryPackage.name)
            .all()
        )

        return bpkgs

    def _get_target_binary_package_map(
        self,
        session,
        suite_name: str,
        component_name: str,
        arch_name: str = None,
        *,
        with_installer: bool = True,
        with_debug: bool = True,
    ):
        if not suite_name:
            suite_name = self._target_suite_name
        log.debug(
            'Retrieving binary package map for destination suite: %s/%s/%s', suite_name, component_name, arch_name
        )

        rss = repo_suite_settings_for(session, self._repo_name, suite_name)
        bpkgs = self._get_target_binary_packages(session, rss, component_name, arch_name, deb_type=DebType.DEB)
        if with_installer:
            bpkgs.extend(
                self._get_target_binary_packages(session, rss, component_name, arch_name, deb_type=DebType.UDEB)
            )

        # include debug repository packages
        if with_debug:
            rss_dbg = repo_suite_settings_for_debug(session, rss)
            if rss_dbg is not None and rss_dbg.id != rss.id:
                bpkgs.extend(
                    self._get_target_binary_packages(session, rss_dbg, component_name, arch_name, deb_type=DebType.DEB)
                )
                if with_installer:
                    bpkgs.extend(
                        self._get_target_binary_packages(
                            session, rss_dbg, component_name, arch_name, deb_type=DebType.UDEB
                        )
                    )

        bpkg_map = {}
        if not with_installer and not with_debug:
            for p in bpkgs:
                bpkg_map[p.name] = p
        else:
            for p in bpkgs:
                ep = bpkg_map.get(p.name)
                if ep and version_compare(ep.version, p.version) >= 0:
                    # package already in the map is newer, so we skip adding the new one
                    continue
                bpkg_map[p.name] = p

        return bpkg_map

    def _import_source_package(self, pkgip: PackageImporter, origin_pkg: ExternalSourcePackage, component: str) -> bool:
        """
        Import a source package from the source repository into the
        target repo.
        """
        dscfile = None
        for f in origin_pkg.files:
            # the source repository might be on a remote location, so we need to
            # request each file to be there.
            # (dak will fetch the files referenced in the .dsc file from the same directory)
            if f.fname.endswith('.dsc'):
                dscfile = self._source_reader.get_file(f)
            self._source_reader.get_file(f)

        if not dscfile:
            log.error(
                'Critical consistency error: Source package {}/{} in repository {} has no .dsc file.'.format(
                    origin_pkg.name, origin_pkg.version, self._source_reader.base_dir
                )
            )
            return False

        # check if the package already exists in our current repository
        rss = pkgip.repo_suite_settings
        session = pkgip.current_session
        ret = session.query(
            exists().where(
                SourcePackage.repo_id == rss.repo_id,
                SourcePackage.name == origin_pkg.name,
                SourcePackage.version == origin_pkg.version,
            )
        ).scalar()
        if ret:
            # the package already exists in this exact version, so we don't need to import it
            # and just need to make it available in the new suite!
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == origin_pkg.name,
                    SourcePackage.version == origin_pkg.version,
                )
                .one()
            )
            copy_source_package(
                session, spkg, rss, include_binaries=True, allow_missing_debug=True, emitter=self._ev_emitter
            )
            self._synced_source_pkgs.append((origin_pkg, PackageSyncState.COPIED))
        else:
            # the package is new to this repository, just import it
            pkgip.import_source(dscfile, component, new_policy=NewPolicy.NEVER_NEW, ignore_bad_section=True)
            self._synced_source_pkgs.append((origin_pkg, PackageSyncState.SYNCED))

        return True

    def _import_binaries_for_sources(
        self,
        session,
        sync_conf: SynchrotronConfig,
        pkgip: PackageImporter,
        component: str,
        spkgs_info: T.Sequence[T.Tuple[ExternalSourcePackage, PackageSyncState]],
        ignore_target_changes: bool = False,
    ) -> bool:
        '''Import binary packages for the given set of source packages into the archive.'''

        if not sync_conf.sync_binaries:
            log.debug('Skipping binary syncs.')
            return True

        # list of valid architectures supported by the target
        target_archs = [a.name for a in sync_conf.destination_suite.architectures]

        # cache of binary-package mappings for the source
        src_bpkg_arch_map = {}
        for aname in target_archs:
            src_bpkg_arch_map[aname] = self._get_source_repo_binary_package_map(
                self._source_suite_name, component, aname
            )

        # cache of binary-package mappings from the target repository/suite/arch
        dest_bpkg_arch_map = {}
        for aname in target_archs:
            dest_bpkg_arch_map[aname] = self._get_target_binary_package_map(
                session, self._target_suite_name, component, aname, with_installer=True, with_debug=True
            )

        for spkg, sync_state in spkgs_info:
            # if a package has been copied, we do not need to attempt
            # to sync any binary packages
            if sync_state == PackageSyncState.COPIED and not ignore_target_changes:
                continue

            bin_files_synced = False
            existing_packages = False
            for arch_name in target_archs:
                if arch_name not in src_bpkg_arch_map:
                    continue

                src_bpkg_map = src_bpkg_arch_map[arch_name]
                dest_bpkg_map = dest_bpkg_arch_map[arch_name]

                bin_files: list[ExternalBinaryPackage] = []
                for bin_i in spkg.expected_binaries:
                    if bin_i.name not in src_bpkg_map:
                        if bin_i.name in dest_bpkg_map:
                            existing_packages = True  # package only exists in target
                        continue
                    if arch_name != 'all' and bin_i.architectures == ['all']:
                        # we handle arch:all explicitly
                        continue
                    bpkg = src_bpkg_map[bin_i.name]
                    if bin_i.version != bpkg.source_version:
                        log.debug(
                            'Not syncing binary package \'{}\': '
                            'Assumed source version \'{}\' of binary does not match actual source version \'{}\'.'.format(
                                bpkg.name,
                                bin_i.version,
                                bpkg.source_version,
                            )
                        )
                        continue

                    ebpkg = dest_bpkg_map.get(bpkg.name)
                    if ebpkg:
                        if version_compare(ebpkg.version, bpkg.version) >= 0:
                            existing_packages = True
                            if sync_state == PackageSyncState.PRESENT:
                                # we don't show a message and just skip this for a package that was already present and where we
                                # are just looking for any binNMUs
                                continue
                            log.debug(
                                'Not syncing binary package \'{}/{}\': '
                                'Existing binary package with bigger/equal version \'{}\' found.'.format(
                                    bpkg.name, bpkg.version, ebpkg.version
                                )
                            )
                            continue

                        # Filter out manual rebuild uploads matching the pattern XbY.
                        # sometimes rebuild uploads of not-modified packages happen, and if the source
                        # distro did a binNMU, we don't want to sync that, even if it's bigger
                        # This rebuild-upload check must only happen if we haven't just updated the source package
                        # (in that case the source package version will be bigger than the existing binary package version)
                        if ebpkg.version.startswith(spkg.version) and version_compare(spkg.version, ebpkg.version) >= 0:
                            if re.match(r'(.*)b([0-9]+)', ebpkg.version) and 'deb' not in ebpkg.version:
                                log.debug(
                                    'Not syncing binary package \'{}/{}\': '
                                    'Existing binary package with rebuild upload found: \'{}\''.format(
                                        bpkg.name, bpkg.version, ebpkg.version
                                    )
                                )
                                existing_packages = True
                                continue

                        if not ignore_target_changes and self._distro_tag in version_revision(ebpkg.version):
                            # safety measure, we should never get here as packages with modifications were
                            # filtered out previously.
                            log.debug(
                                'Can not sync binary package {}/{}: Target has modifications.'.format(
                                    bin_i.name, bin_i.version
                                )
                            )
                            existing_packages = True
                            continue

                    bin_files.append(bpkg)

                # check if we're only missing debug packages, if we have existing binaries, but also
                # some missing binaries
                if existing_packages and bin_files:
                    only_debug_missing = True
                    for orig_bpkg in bin_files:
                        if orig_bpkg.override.section != 'debug':
                            only_debug_missing = False
                            break
                    if only_debug_missing:
                        # If only debug packages are missing, it indicates that we maybe do not accept them in their
                        # destinations at all, so we just short-circuit here and skip remaining syncs.
                        # A better solution would probably be to detect earlier and not even get here for debug
                        # packages designated to a non-debug-accepting suite/repo combination.
                        log.debug(
                            'Only debug packages missing for %s/%s in %s, not syncing remaining binaries.',
                            arch_name,
                            spkg.name,
                            spkg.version,
                        )
                        continue

                # now import the binary packages, if there is anything to import
                if bin_files:
                    bin_files_synced = True
                    for orig_bpkg in bin_files:
                        fname = self._source_reader.get_file(orig_bpkg.bin_file)
                        try:
                            pkgip.import_binary(fname, component, ignore_missing_override=True)
                        except ArchivePackageExistsError as e:
                            # package exists, but apparently is located in a different suite
                            # this may be due to a previous crash or bug, we try to recover from it here
                            ebpkg = (
                                session.query(BinaryPackage)
                                .filter(
                                    BinaryPackage.name == orig_bpkg.name,
                                    BinaryPackage.version == orig_bpkg.version,
                                    BinaryPackage.repo.has(id=pkgip.repo_suite_settings.repo_id),
                                    BinaryPackage.component.has(name=component),
                                    BinaryPackage.architecture.has(name=arch_name),
                                )
                                .one_or_none()
                            )
                            if not ebpkg:
                                raise e
                            log.debug(
                                (
                                    'Found preexisting binary package %s/%s in repo after trying to import '
                                    'an already exisiting package into our target suite.'
                                ),
                                ebpkg.name,
                                ebpkg.version,
                            )

                            # we "undelete" a package here in case it has been expired in the target and we still
                            # sync it - this may happen especially when syncing updates/security suites
                            ebpkg.time_deleted = None

                            new_suite = pkgip.repo_suite_settings.suite
                            if new_suite not in ebpkg.suites:
                                log.warning(
                                    (
                                        'Added preexisting binary package %s/%s to new suite %s '
                                        '(assuming it is identical with file from origin)'
                                    ),
                                    ebpkg.name,
                                    ebpkg.version,
                                    new_suite.name,
                                )
                                ebpkg.suites.append(new_suite)
                                package_mark_published(session, pkgip.repo_suite_settings, ebpkg)

            if not bin_files_synced and not existing_packages:
                log.warning('No binary packages synced for source {}/{}'.format(spkg.name, spkg.version))

        return True

    def _sync_packages_internal(self, session, component_name: str, pkgnames: list[str], force: bool = False):
        self._synced_source_pkgs = []

        sync_source = self._get_sync_source(session)
        sync_conf = (
            session.query(SynchrotronConfig)
            .filter(
                SynchrotronConfig.repo.has(name=self._repo_name),
                SynchrotronConfig.source_id == sync_source.id,
                SynchrotronConfig.destination_suite.has(name=self._target_suite_name),
            )
            .one_or_none()
        )
        if not sync_conf:
            log.error('Unable to find a sync config for this source/destination combination.')
            return False

        if not sync_conf.sync_enabled:
            log.error('Can not synchronize package: Synchronization is disabled for this configuration.')
            return False

        dest_pkg_map = self._get_target_source_package_map(session, component_name)
        src_pkg_map = self._get_source_repo_source_package_map(self._source_suite_name, component_name)

        rss = repo_suite_settings_for(session, self._repo_name, self._target_suite_name)
        pkgip = PackageImporter(session, rss)
        pkgip.keep_source_packages = True

        for pkgname in pkgnames:
            spkg = src_pkg_map.get(pkgname)
            dpkg = dest_pkg_map.get(pkgname)

            if not spkg:
                log.info('Can not sync {}: Does not exist in source.'.format(pkgname))
                continue
            if pkgname in self._sync_blacklist:
                log.info('Can not sync {}: The package is blacklisted.'.format(pkgname))
                continue

            if dpkg:
                if version_compare(dpkg.version, spkg.version) >= 0:
                    if force:
                        log.warning(
                            '{}: Target version \'{}\' is newer than or equal to source version \'{}\'.'.format(
                                pkgname, dpkg.version, spkg.version
                            )
                        )
                    else:
                        log.info(
                            'Can not sync {}: Target version \'{}\' is newer than or equal to source version \'{}\'.'.format(
                                pkgname, dpkg.version, spkg.version
                            )
                        )
                        continue

                if not force:
                    if self._distro_tag in version_revision(dpkg.version):
                        log.error(
                            'Not syncing {}/{}: Destination has modifications (found {}).'.format(
                                spkg.name, spkg.version, dpkg.version
                            )
                        )
                        continue

            # sync source package
            # the source package must always be known first
            ret = self._import_source_package(pkgip, spkg, component_name)
            if not ret:
                return False

        ret = self._import_binaries_for_sources(
            session, sync_conf, pkgip, component_name, self._synced_source_pkgs, force
        )

        # TODO: Analyze the input, fetch the packages from the source distribution and
        # import them into the target in their correct order.
        # Then apply the correct, synced override from the source distro.

        self._publish_synced_spkg_events(
            sync_conf.source.os_name, sync_conf.source.suite_name, sync_conf.destination_suite.name, force
        )
        return ret

    def sync_packages(self, component_name: str, pkgnames: list[str], force: bool = False):
        """Sync a select set of packages manually."""

        with process_file_lock('sync_{}'.format(self._repo_name)), process_file_lock(
            'archive_expire-{}'.format(self._repo_name), wait=True
        ):
            with session_scope() as session:
                return self._sync_packages_internal(session, component_name, pkgnames, force)

    def _emit_new_issue_event(self, autosync, issue):
        data = {
            'name': issue.package_name,
            'src_os': autosync.source.os_name,
            'suite_src': issue.source_suite,
            'suite_dest': issue.target_suite,
            'version_src': issue.source_version,
            'version_dest': issue.target_version,
            'kind': str(issue.kind),
        }

        self._ev_emitter.submit_event('new-autosync-issue', data)

    def _is_candidate(self, spkg: ExternalSourcePackage, dpkg: SourcePackage):
        if version_compare(dpkg.version, spkg.version) >= 0:
            log.debug(
                'Skipped sync of {}: Target version \'{}\' is equal/newer than source version \'{}\'.'.format(
                    spkg.name, dpkg.version, spkg.version
                )
            )
            return False
        return True

    def _autosync_internal(self, session, remove_cruft: bool = True) -> bool:
        """Synchronize all packages between source and destination."""

        self._synced_source_pkgs = []
        binary_sync_todo: list[
            T.Tuple[ExternalSourcePackage, PackageSyncState]
        ] = []  # source packages which should have their binary packages updated
        known_issues = []

        sync_source = self._get_sync_source(session)
        sync_conf = (
            session.query(SynchrotronConfig)
            .filter(
                SynchrotronConfig.repo.has(name=self._repo_name),
                SynchrotronConfig.source_id == sync_source.id,
                SynchrotronConfig.destination_suite.has(name=self._target_suite_name),
            )
            .one_or_none()
        )

        if not sync_conf.sync_enabled or not sync_conf.sync_auto_enabled:
            raise Exception('Will not perform autosync on disabled configuration.')

        log.info(
            'Synchronizing packages from {}/{} with {}/{}'.format(
                sync_conf.source.os_name,
                sync_conf.source.suite_name,
                sync_conf.repo.name,
                sync_conf.destination_suite.name,
            )
        )

        # obtain package import helper to register new packages with the archive
        rss = repo_suite_settings_for(session, self._repo_name, self._target_suite_name)
        pkgip = PackageImporter(session, rss)
        pkgip.keep_source_packages = True

        for component in rss.suite.components:
            if component.name not in sync_source.components:
                log.warning(
                    'Will not sync packages from component "%s" to target %s: Component does not exist in source suite.',
                    component.name,
                    rss.suite.name,
                )
                continue

            dest_pkg_map = self._get_target_source_package_map(session, component.name)

            # The source package lists contains many different versions, some source package
            # versions are explicitly kept for GPL-compatibility.
            # Sometimes a binary package migrates into another suite, dragging a newer source-package
            # that it was built against with itself into the target suite.
            # These packages then have a source with a high version number, but might not have any
            # binaries due to them migrating later.
            # We need to care for that case when doing binary syncs (TODO: and maybe safeguard against it
            # when doing source-only syncs too?), That's why we don't filter out the newest packages in
            # binary-sync-mode.
            if sync_conf.sync_binaries:
                src_pkg_range = self._get_source_repo_source_packages(self._source_suite_name, component.name)
            else:
                src_pkg_range = self._get_source_repo_source_package_map(
                    self._source_suite_name, component.name
                ).values()

            # determine initial sync candidates - comparing a lot ov versions can be slow,
            # and since the version comparison is implemented in C, we can use a ThreadPool here
            # to speed things up slightly.
            candidates = []
            with ThreadPool() as pool:
                tasks_pending = []
                for spkg in src_pkg_range:
                    # ignore blacklisted packages in automatic sync
                    if spkg.name in self._sync_blacklist:
                        continue

                    dpkg = dest_pkg_map.get(spkg.name)
                    if dpkg:
                        if dpkg.version == spkg.version and self._distro_tag not in version_revision(dpkg.version):
                            if rss.suite in dpkg.suites:
                                # check if the target package (if an exact match) has its binaries, and try to import them
                                # again if they are missing. This code exists to recover from incomplete syncs in case a
                                # previous autosync run was interrupted for any reason.
                                if not dpkg.binaries:
                                    binary_sync_todo.append((spkg, PackageSyncState.SYNCED))
                                else:
                                    # we need to add the package here even if nothing was done to it, so we can
                                    # later sync any binNMUs done in the origin OS in case we do perform binary syncs.
                                    binary_sync_todo.append((spkg, PackageSyncState.PRESENT))
                            continue

                        tasks_pending.append((spkg, dpkg, pool.schedule(self._is_candidate, (spkg, dpkg))))
                    else:
                        candidates.append((spkg, None))

                for spkg, dpkg, is_candidate_future in tasks_pending:
                    if is_candidate_future.result():
                        candidates.append((spkg, dpkg))

            # test the initial candidates further and actually sync them if they are suitable
            for spkg, dpkg in candidates:
                if dpkg:
                    # check if we have a modified target package,
                    # indicated via its Debian revision, e.g. "1.0-0tanglu1"
                    if self._distro_tag in version_revision(dpkg.version):
                        log.info(
                            'Not syncing {}/{}: Destination has modifications (found {}).'.format(
                                spkg.name, spkg.version, dpkg.version
                            )
                        )

                        # add information that this package needs to be merged to the issue list
                        issue = (
                            session.query(SynchrotronIssue)
                            .filter(
                                SynchrotronIssue.config_id == sync_conf.id, SynchrotronIssue.package_name == dpkg.name
                            )
                            .one_or_none()
                        )
                        issue_new = False
                        if not issue:
                            issue = SynchrotronIssue()
                            issue.config = sync_conf
                            issue.package_name = spkg.name
                            issue_new = True
                            session.add(issue)
                        issue.kind = SynchrotronIssueKind.MERGE_REQUIRED
                        issue.source_version = spkg.version
                        issue.target_version = dpkg.version
                        issue.source_suite = self._source_suite_name
                        issue.target_suite = self._target_suite_name
                        if issue_new:
                            self._emit_new_issue_event(sync_conf, issue)

                        known_issues.append(issue)
                        continue

                # sync source package
                # the source package must always be known first
                ret = self._import_source_package(pkgip, spkg, component.name)
                if not ret:
                    return False

                # a new source package is always active and needs its binary packages synced, in
                # case we do binary syncs.
                binary_sync_todo.append((spkg, PackageSyncState.SYNCED))

            # import binaries as well. We test for binary updates for all available active source packages,
            # as binNMUs might have happened in the source distribution.
            # (an active package in this context is any source package which doesn't have modifications in the
            # target distribution)
            ret = self._import_binaries_for_sources(session, sync_conf, pkgip, component.name, binary_sync_todo)
            if not ret:
                return False

        # test for cruft packages
        target_pkg_index = {}
        for component in rss.suite.components:
            dest_pkg_map = self._get_target_source_package_map(session, component.name, suite_name=rss.suite.name)
            for pkgname, pkg in dest_pkg_map.items():
                target_pkg_index[pkgname] = pkg

        # check which packages are present in the target, but not in the source suite
        for component in rss.suite.components:
            if component.name not in sync_source.components:
                continue
            src_pkg_map = self._get_source_repo_source_package_map(self._source_suite_name, component.name)
            for pkgname in src_pkg_map.keys():
                target_pkg_index.pop(pkgname, None)

        # remove cruft packages
        if remove_cruft:
            log.debug('Attempting to locate orphaned/cruft packages')
            for pkgname, dpkg in target_pkg_index.items():
                dpkg_ver_revision = version_revision(dpkg.version, False)
                # native packages are never removed
                if not dpkg_ver_revision:
                    continue

                # check if the package is introduced as new in the distro, in which case we won't remove it
                if dpkg_ver_revision.startswith('0' + self._distro_tag):
                    continue

                # if this package was modified in the target distro, we will also not remove it, but flag it
                # as "potential cruft" for someone to look at.
                if self._distro_tag in dpkg_ver_revision:
                    issue = (
                        session.query(SynchrotronIssue)
                        .filter(SynchrotronIssue.config_id == sync_conf.id, SynchrotronIssue.package_name == dpkg.name)
                        .one_or_none()
                    )
                    issue_new = False
                    if not issue:
                        issue = SynchrotronIssue()
                        issue.config = sync_conf
                        issue.package_name = dpkg.name
                        issue_new = True
                        session.add(issue)
                    issue.kind = SynchrotronIssueKind.MAYBE_CRUFT
                    issue.source_suite = self._source_suite_name
                    issue.target_suite = self._target_suite_name
                    issue.source_version = None
                    issue.target_version = dpkg.version
                    if issue_new:
                        self._emit_new_issue_event(sync_conf, issue)

                    known_issues.append(issue)
                    continue
                else:
                    # we can most likely remove this package
                    # TODO: We should implement a smart way to auto-remove the package here, possibly running debcheck
                    # on the archive with the package dropped and see if it results in packages becoming non-installable.
                    issue = (
                        session.query(SynchrotronIssue)
                        .filter(SynchrotronIssue.config_id == sync_conf.id, SynchrotronIssue.package_name == dpkg.name)
                        .one_or_none()
                    )
                    issue_new = False
                    if not issue:
                        issue = SynchrotronIssue()
                        issue.config = sync_conf
                        issue.package_name = dpkg.name
                        issue_new = True
                        session.add(issue)

                    issue.kind = SynchrotronIssueKind.REMOVAL_FAILED
                    issue.source_suite = self._source_suite_name
                    issue.target_suite = self._target_suite_name
                    issue.source_version = None
                    issue.target_version = dpkg.version
                    issue.details = 'This package needs manual removal.'
                    if issue_new:
                        self._emit_new_issue_event(sync_conf, issue)

                    known_issues.append(issue)

        self._publish_synced_spkg_events(
            sync_conf.source.os_name, sync_conf.source.suite_name, sync_conf.destination_suite.name, False
        )

        # delete cruft
        log.info('Cleaning up resolved sync issues')
        existing_sync_issues = {}
        all_issues = (
            session.query(SynchrotronIssue)
            .filter(
                SynchrotronIssue.config_id == sync_conf.id,
            )
            .all()
        )
        for eissue in all_issues:
            eid = '{}-{}-{}:{}'.format(
                eissue.package_name, eissue.source_version, eissue.target_version, str(eissue.kind)
            )
            existing_sync_issues[eid] = eissue

        for info in known_issues:
            eid = '{}-{}-{}:{}'.format(info.package_name, info.source_version, info.target_version, str(info.kind))
            existing_sync_issues.pop(eid, None)

        for eissue in existing_sync_issues.values():
            session.delete(eissue)

            data = {
                'name': eissue.package_name,
                'src_os': sync_conf.source.os_name,
                'suite_src': eissue.source_suite,
                'suite_dest': eissue.target_suite,
                'version_src': eissue.source_version,
                'version_dest': eissue.target_version,
                'kind': str(eissue.kind),
            }

            self._ev_emitter.submit_event('resolved-autosync-issue', data)

        return True

    def autosync(self, remove_cruft: bool = True) -> bool:
        """Synchronize all packages between source and destination."""

        with (
            process_file_lock('sync_{}'.format(self._repo_name)),
            process_file_lock('publish_{}-{}'.format(self._repo_name, self._target_suite_name), wait=True),
            process_file_lock('archive_expire-{}'.format(self._repo_name), wait=True),
        ):
            with session_scope() as session:
                ret = self._autosync_internal(session, remove_cruft)

            # cleanup cruft, as we may have downloaded a lot of packages
            self._source_reader.cleanup()

            return ret
