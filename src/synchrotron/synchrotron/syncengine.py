# Copyright (C) 2016-2020 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import re
from typing import List
from apt_pkg import version_compare
from laniakea import LocalConfig, LkModule
from laniakea.repository import Repository, make_newest_packages_dict, version_revision
from laniakea.db import session_scope, config_get_distro_tag, \
    ArchiveSuite, ArchiveComponent, ArchiveArchitecture, SourcePackage, SynchrotronIssue, \
    SynchrotronIssueKind, SynchrotronSource, SynchrotronConfig, SyncBlacklistEntry
from laniakea.dakbridge import DakBridge
from laniakea.logging import log
from laniakea.msgstream import EventEmitter


class SyncEngine:
    '''
    Execute package synchronization in Synchrotron
    '''

    def __init__(self, target_suite_name: str, source_suite_name: str):
        self._lconf = LocalConfig()
        self._dak = DakBridge()

        # FIXME: Don't hardcode this!
        repo_name = 'master'

        # the repository of the distribution we import stuff into
        self._target_repo = Repository(self._lconf.archive_root_dir,
                                       repo_name)
        self._target_repo.set_trusted(True)

        self._target_suite_name = target_suite_name
        self._source_suite_name = source_suite_name
        self._distro_tag = config_get_distro_tag()
        self._synced_source_pkgs: list[SourcePackage] = []

        with session_scope() as session:
            sync_source = session.query(SynchrotronSource) \
                                 .filter(SynchrotronSource.suite_name == self._source_suite_name).one()

            # FIXME: Synchrotron needs adjustments to work
            # better with the new "multiple autosync tasks" model.
            # This code will need to be revised for that
            # (currently it is just a 1:1 translation from D code)

            # the repository of the distribution we use to sync stuff from
            self._source_repo = Repository(sync_source.repo_url,
                                           sync_source.os_name,
                                           self._lconf.synchrotron_sourcekeyrings)

        # we trust everything by default
        self._imports_trusted = True

        with session_scope() as session:
            self._sync_blacklist = set([value for value, in session.query(SyncBlacklistEntry.pkgname)])

    def _publish_synced_spkg_events(self, src_os, src_suite, dest_suite, forced=False, emitter=None):
        ''' Submit events for the synced source packages to the message stream '''
        if not emitter:
            emitter = EventEmitter(LkModule.SYNCHROTRON)
        for spkg in self._synced_source_pkgs:
            data = {'name': spkg.name,
                    'version': spkg.version,
                    'src_os': src_os,
                    'suite_src': src_suite,
                    'suite_dest': dest_suite,
                    'forced': forced}

            emitter.submit_event('src-package-imported', data)

    def _get_repo_source_package_map(self, repo, suite_name: str, component_name: str):
        ''' Get an associative array of the newest source packages present in a repository. '''

        suite = ArchiveSuite(suite_name)
        component = ArchiveComponent(component_name)
        spkgs = repo.source_packages(suite, component)
        return make_newest_packages_dict(spkgs)

    def _get_repo_binary_package_map(self, repo, suite_name: str, component_name: str,
                                     arch_name: str = None, with_installer: bool = True):
        ''' Get an associative array of the newest binary packages present in a repository. '''

        suite = ArchiveSuite(suite_name)
        component = ArchiveComponent(component_name)
        arch = ArchiveArchitecture(arch_name)
        arch_all = ArchiveArchitecture('all')
        bpkgs = repo.binary_packages(suite, component, arch)
        bpkgs.extend(repo.binary_packages(suite, component, arch_all))  # always append arch:all packages

        if with_installer:
            # add d-i packages to the mix
            bpkgs.extend(repo.installer_packages(suite, component, arch))
            bpkgs.extend(repo.installer_packages(suite, component, arch_all))  # always append arch:all packages
        return make_newest_packages_dict(bpkgs)

    def _get_target_source_packages(self, component: str):
        ''' Get mapping of all sources packages in a suite and its parent suite. '''
        with session_scope() as session:
            target_suite = session.query(ArchiveSuite) \
                                  .filter(ArchiveSuite.name == self._target_suite_name).one()
            suite_pkgmap = self._get_repo_source_package_map(self._target_repo,
                                                             target_suite.name,
                                                             component)
            if target_suite.parent:
                # we have a parent suite
                parent_map = self._get_repo_source_package_map(self._target_repo,
                                                               target_suite.parent.name,
                                                               component)

                # merge the two arrays, keeping only the latest versions
                suite_pkgmap = make_newest_packages_dict(list(parent_map.values()) + list(suite_pkgmap.values()))

        return suite_pkgmap

    def _import_package_files(self, suite: str, component: str, fnames: List[str]):
        ''' Import an arbitrary amount of packages via the archive management software. '''
        return self._dak.import_package_files(suite, component, fnames, self._imports_trusted, True)

    def _import_source_package(self, spkg: SourcePackage, component: str) -> bool:
        '''
        Import a source package from the source repository into the
        target repo.
        '''
        dscfile = None
        for f in spkg.files:
            # the source repository might be on a remote location, so we need to
            # request each file to be there.
            # (dak will fetch the files referenced in the .dsc file from the same directory)
            if f.fname.endswith('.dsc'):
                dscfile = self._source_repo.get_file(f)
            self._source_repo.get_file(f)

        if not dscfile:
            log.error('Critical consistency error: Source package {} in repository {} has no .dsc file.'
                      .format(spkg.name, self._source_repo.base_dir))
            return False

        if self._import_package_files(self._target_suite_name, component, [dscfile]):
            self._synced_source_pkgs.append(spkg)
            return True
        return False

    def _import_binaries_for_source(self, sync_conf, target_suite, component: str, spkgs: List[SourcePackage],
                                    ignore_target_changes: bool = False) -> bool:
        ''' Import binary packages for the given set of source packages into the archive. '''

        if not sync_conf.sync_binaries:
            log.debug('Skipping binary syncs.')
            return True

        # list of valid architectrures supported by the target
        target_archs = [a.name for a in target_suite.architectures]

        # cache of binary-package mappings for the source
        src_bpkg_arch_map = {}
        for aname in target_archs:
            src_bpkg_arch_map[aname] = self._get_repo_binary_package_map(self._source_repo, self._source_suite_name, component, aname)

        # cache of binary-package mappings from the target repository
        dest_bpkg_arch_map = {}
        for aname in target_archs:
            dest_bpkg_arch_map[aname] = self._get_repo_binary_package_map(self._target_repo, self._target_suite_name, component, aname)

        for spkg in spkgs:
            bin_files_synced = False
            existing_packages = False
            for arch_name in target_archs:
                if arch_name not in src_bpkg_arch_map:
                    continue

                src_bpkg_map = src_bpkg_arch_map[arch_name]
                dest_bpkg_map = dest_bpkg_arch_map[arch_name]

                bin_files = []
                for bin_i in spkg.binaries:
                    if bin_i.name not in src_bpkg_map:
                        if bin_i.name in dest_bpkg_map:
                            existing_packages = True  # package only exists in target
                        continue
                    if arch_name != 'all' and bin_i.architectures == ['all']:
                        # we handle arch:all explicitly
                        continue
                    bpkg = src_bpkg_map[bin_i.name]
                    if bin_i.version != bpkg.source_version:
                        log.debug('Not syncing binary package \'{}\': Version number \'{}\' does not match source package version \'{}\'.'
                                  .format(bpkg.name, bin_i.version, bpkg.source_version))
                        continue

                    ebpkg = dest_bpkg_map.get(bpkg.name)
                    if ebpkg:
                        if version_compare(ebpkg.version, bpkg.version) >= 0:
                            log.debug('Not syncing binary package \'{}/{}\': Existing binary package with bigger/equal version \'{}\' found.'
                                      .format(bpkg.name, bpkg.version, ebpkg.version))
                            existing_packages = True
                            continue

                        # Filter out manual rebuild uploads matching the pattern XbY.
                        # sometimes rebuild uploads of not-modified packages happen, and if the source
                        # distro did a binNMU, we don't want to sync that, even if it's bigger
                        # This rebuild-upload check must only happen if we haven't just updated the source package
                        # (in that case the source package version will be bigger than the existing binary package version)
                        if version_compare(spkg.version, ebpkg.version) >= 0:
                            if re.match(r'(.*)b([0-9]+)', ebpkg.version):
                                log.debug('Not syncing binary package \'{}/{}\': Existing binary package with rebuild upload \'{}\' found.'
                                          .format(bpkg.name, bpkg.version, ebpkg.version))
                                existing_packages = True
                                continue

                        if not ignore_target_changes and self._distro_tag in version_revision(ebpkg.version):
                            # safety measure, we should never get here as packages with modifications were
                            # filtered out previously.
                            log.debug('Can not sync binary package {}/{}: Target has modifications.'.format(bin_i.name, bin_i.version))
                            continue

                    fname = self._source_repo.get_file(bpkg.bin_file)
                    bin_files.append(fname)

                # now import the binary packages, if there is anything to import
                if bin_files:
                    bin_files_synced = True
                    ret = self._import_package_files(self._target_suite_name, component, bin_files)
                    if not ret:
                        return False

            if not bin_files_synced and not existing_packages:
                log.warning('No binary packages synced for source {}/{}'.format(spkg.name, spkg.version))

        return True

    def sync_packages(self, component: str, pkgnames: List[str], force: bool = False):
        self._synced_source_pkgs = []

        with session_scope() as session:
            sync_conf = session.query(SynchrotronConfig) \
                               .join(SynchrotronConfig.destination_suite) \
                               .join(SynchrotronConfig.source) \
                               .filter(ArchiveSuite.name == self._target_suite_name,
                                       SynchrotronSource.suite_name == self._source_suite_name).one_or_none()
            if not sync_conf:
                log.error('Unable to find a sync config for this source/destination combination.')
                return False

            if not sync_conf.sync_enabled:
                log.error('Can not synchronize package: Synchronization is disabled for this configuration.')
                return False

            target_suite = session.query(ArchiveSuite) \
                                  .filter(ArchiveSuite.name == self._target_suite_name).one()

            dest_pkg_map = self._get_target_source_packages(component)
            src_pkg_map = self._get_repo_source_package_map(self._source_repo,
                                                            self._source_suite_name,
                                                            component)

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
                            log.warning('{}: Target version \'{}\' is newer/equal than source version \'{}\'.'
                                        .format(pkgname, dpkg.version, spkg.version))
                        else:
                            log.info('Can not sync {}: Target version \'{}\' is newer/equal than source version \'{}\'.'
                                     .format(pkgname, dpkg.version, spkg.version))
                            continue

                    if not force:
                        if self._distro_tag in version_revision(dpkg.version):
                            log.error('Not syncing {}/{}: Destination has modifications (found {}).'
                                      .format(spkg.name, spkg.version, dpkg.version))
                            continue

                # sync source package
                # the source package must always be known to dak first
                ret = self._import_source_package(spkg, component)
                if not ret:
                    return False

            ret = self._import_binaries_for_source(sync_conf, target_suite, component, self._synced_source_pkgs, force)

            # TODO: Analyze the input, fetch the packages from the source distribution and
            # import them into the target in their correct order.
            # Then apply the correct, synced override from the source distro.

            self._publish_synced_spkg_events(sync_conf.source.os_name,
                                             sync_conf.source.suite_name,
                                             sync_conf.destination_suite.name,
                                             force)
            return ret

    def autosync(self, session, sync_conf, remove_cruft: bool = True):
        ''' Synchronize all packages that are newer '''

        self._synced_source_pkgs = []
        active_src_pkgs = []  # source packages which should have their binary packages updated
        res_issues = []

        target_suite = session.query(ArchiveSuite) \
                              .filter(ArchiveSuite.name == self._target_suite_name).one()
        sync_conf = session.query(SynchrotronConfig) \
                           .join(SynchrotronConfig.destination_suite) \
                           .join(SynchrotronConfig.source) \
                           .filter(ArchiveSuite.name == self._target_suite_name,
                                   SynchrotronSource.suite_name == self._source_suite_name).one_or_none()

        for component in target_suite.components:
            dest_pkg_map = self._get_target_source_packages(component.name)

            # The source package lists contains many different versions, some source package
            # versions are explicitly kept for GPL-compatibility.
            # Sometimes a binary package migrates into another suite, dragging a newer source-package
            # that it was built against with itslf into the target suite.
            # These packages then have a source with a high version number, but might not have any
            # binaries due to them migrating later.
            # We need to care for that case when doing binary syncs (TODO: and maybe safeguard against it
            # when doing source-only syncs too?), That's why we don't filter out the newest packages in
            # binary-sync-mode.
            if sync_conf.sync_binaries:
                src_pkg_range = self._source_repo.source_packages(ArchiveSuite(self._source_suite_name), component)
            else:
                src_pkg_range = self._get_repo_source_package_map(self._source_repo,
                                                                  self._source_suite_name,
                                                                  component).values()

            for spkg in src_pkg_range:
                # ignore blacklisted packages in automatic sync
                if spkg.name in self._sync_blacklist:
                    continue

                dpkg = dest_pkg_map.get(spkg.name)
                if dpkg:
                    if version_compare(dpkg.version, spkg.version) >= 0:
                        log.debug('Skipped sync of {}: Target version \'{}\' is equal/newer than source version \'{}\'.'
                                  .format(spkg.name, dpkg.version, spkg.version))
                        continue

                    # check if we have a modified target package,
                    # indicated via its Debian revision, e.g. "1.0-0tanglu1"
                    if self._distro_tag in version_revision(dpkg.version):
                        log.info('Not syncing {}/{}: Destination has modifications (found {}).'
                                 .format(spkg.name, spkg.version, dpkg.version))

                        # add information that this package needs to be merged to the issue list
                        issue = SynchrotronIssue()
                        issue.kind = SynchrotronIssueKind.MERGE_REQUIRED
                        issue.package_name = spkg.name
                        issue.source_version = spkg.version
                        issue.target_version = dpkg.version
                        issue.source_suite = self._source_suite_name
                        issue.target_suite = self._target_suite_name

                        res_issues.append(issue)
                        continue

                # sync source package
                # the source package must always be known to dak first
                ret = self._import_source_package(spkg, component.name)
                if not ret:
                    return False, []

                # a new source package is always active and needs it's binary packages synced, in
                # case we do binary syncs.
                active_src_pkgs.append(spkg)

            # all packages in the target distribution are considered active, as long as they don't
            # have modifications.
            for spkg in dest_pkg_map.values():
                if self._distro_tag in version_revision(spkg.version):
                    active_src_pkgs.append(spkg)

            # import binaries as well. We test for binary updates for all available active source packages,
            # as binNMUs might have happened in the source distribution.
            # (an active package in this context is any source package which doesn't have modifications in the
            # target distribution)
            ret = self._import_binaries_for_source(sync_conf, target_suite, component.name, active_src_pkgs)
            if not ret:
                return False, []

        # test for cruft packages
        target_pkg_index = {}
        for component in target_suite.components:
            dest_pkg_map = self._get_repo_source_package_map(self._target_repo,
                                                             target_suite.name,
                                                             component.name)
            for pkgname, pkg in dest_pkg_map.items():
                target_pkg_index[pkgname] = pkg

        # check which packages are present in the target, but not in the source suite
        for component in target_suite.components:
            src_pkg_map = self._get_repo_source_package_map(self._source_repo,
                                                            self._source_suite_name,
                                                            component.name)
            for pkgname in src_pkg_map.keys():
                target_pkg_index.pop(pkgname, None)

        # remove cruft packages
        if remove_cruft:
            for pkgname, dpkg in target_pkg_index.items():
                dpkg_ver_revision = version_revision(dpkg.version, False)
                # native packages are never removed
                if not dpkg_ver_revision:
                    continue

                # check if the package is intoduced as new in the distro, in which case we won't remove it
                if dpkg_ver_revision.startswith('0' + self._distro_tag):
                    continue

                # if this package was modified in the target distro, we will also not remove it, but flag it
                # as "potential cruft" for someone to look at.
                if self._distro_tag in dpkg_ver_revision:
                    issue = SynchrotronIssue()
                    issue.kind = SynchrotronIssueKind.MAYBE_CRUFT
                    issue.source_suite = self._source_suite_name
                    issue.target_suite = self._target_suite_name
                    issue.package_name = dpkg.name
                    issue.source_version = None
                    issue.target_version = dpkg.version

                    res_issues.append(issue)
                    continue

                # check if we can remove this package without breaking stuff
                if self._dak.package_is_removable(dpkg.name, target_suite.name):
                    # try to remove the package
                    try:
                        self._dak.remove_package(dpkg.name, target_suite.name)
                    except Exception as e:
                        issue = SynchrotronIssue()
                        issue.kind = SynchrotronIssueKind.REMOVAL_FAILED
                        issue.source_suite = self._source_suite_name
                        issue.target_suite = self._target_suite_name
                        issue.package_name = dpkg.name
                        issue.source_version = None
                        issue.target_version = dpkg.version
                        issue.details = str(e)

                        res_issues.append(issue)
                else:
                    # looks like we can not remove this
                    issue = SynchrotronIssue()
                    issue.kind = SynchrotronIssueKind.REMOVAL_FAILED
                    issue.source_suite = self._source_suite_name
                    issue.target_suite = self._target_suite_name
                    issue.package_name = dpkg.name
                    issue.source_version = None
                    issue.target_version = dpkg.version
                    issue.details = 'This package can not be removed without breaking other packages. It needs manual removal.'

                    res_issues.append(issue)

        self._publish_synced_spkg_events(sync_conf.source.os_name,
                                         sync_conf.source.suite_name,
                                         sync_conf.destination_suite.name,
                                         False)

        return True, res_issues
