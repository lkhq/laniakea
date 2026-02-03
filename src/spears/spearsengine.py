# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from __future__ import annotations

import os
import gzip
import shutil
import subprocess
from uuid import uuid4

from pebble import concurrent
from apt_pkg import TagFile

import laniakea.typing as T
from laniakea.db import (
    LkModule,
    SpearsHint,
    ArchiveSuite,
    SpearsExcuse,
    SourcePackage,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    SpearsMigrationTask,
    session_scope,
)
from laniakea.utils import listify, open_compressed
from laniakea.logging import log
from laniakea.msgstream import EventEmitter
from laniakea.reporeader import RepositoryReader
from laniakea.localconfig import LocalConfig

from .britney import Britney
from .excuses import ExcusesFile
from .britneyconfig import BritneyConfig


class SpearsEngine:
    '''
    Run package migrations using Britney and manage its configurations.
    '''

    def __init__(self):
        self._lconf = LocalConfig()
        self._britney = Britney()

        self._workspace = os.path.join(self._lconf.workspace, 'spears')
        os.makedirs(self._workspace, exist_ok=True)

        my_dir = os.path.dirname(os.path.realpath(__file__))
        self._lk_archive_exe = os.path.normpath(os.path.join(my_dir, '..', 'lkarchive', 'lk-archive.py'))
        if not os.path.isfile(self._lk_archive_exe):
            self._lk_archive_exe = 'lk-archive'

    def _get_suites_dists_staging_dir(self, mi_workspace: str, suites: T.Union[ArchiveSuite, T.List[ArchiveSuite]]):
        '''
        If our source suite is a single suite, we use the archive's vanilla data, but with arch:all
        merged into the arch:any files.
        If we use Britney to migrate packages from two suites together however, we need
        an amalgamation of the two suites' Packages/Sources files, which resides in Britney's
        workspace directory.
        This function returns the correct dists/ path, where the preprocessed data for Britney
        is written to.
        '''

        if not suites:
            raise Exception('Can not get source-suite dists/ directory if no source suites are selected.')
        suites = listify(suites)

        if len(suites) == 1:
            dists_dir = os.path.join(mi_workspace, 'input', 'dists', suites[0].name)
        else:
            dists_dir = os.path.join(mi_workspace, 'input', 'dists', '+'.join([s.name for s in suites]))

        os.makedirs(dists_dir, exist_ok=True)
        return dists_dir

    def _get_migration_displayname(
        self, repo: ArchiveRepository, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite
    ) -> str:
        return '{}: {} -> {}'.format(repo.name, '+'.join(sorted([s.name for s in suites_from])), suite_to.name)

    def _get_migrate_workspace(self, mtask: SpearsMigrationTask) -> str:
        return os.path.join(self._workspace, mtask.repo.name, mtask.make_migration_shortname())

    def update_config(self, update_britney: bool = True):
        """
        Update configuration and distribution
        copy of Britney
        """

        from laniakea.userhints import UserHints

        log.info('Updating configuration')

        uhints = UserHints()
        uhints.load(update=True)
        try:
            uhints.update_spears_hints()
        except Exception as e:
            log.error('Failed to import user hints from Git: %s', str(e))

        with session_scope() as session:
            for mtask in session.query(SpearsMigrationTask).all():
                suites_from = mtask.source_suites
                suite_to = mtask.target_suite
                assert len(suites_from) >= 1
                assert suite_to

                log.info(
                    'Refreshing Britney config for "{}"'.format(
                        self._get_migration_displayname(mtask.repo, suites_from, suite_to)
                    )
                )
                mi_wspace = self._get_migrate_workspace(mtask)
                bc = BritneyConfig(mi_wspace)
                bc.set_archive_paths(
                    self._get_suites_dists_staging_dir(mi_wspace, suites_from),
                    self._get_suites_dists_staging_dir(mi_wspace, suite_to),
                )
                bc.set_components([c.name for c in suite_to.components])
                bc.set_architectures([a.name for a in suite_to.architectures])
                bc.set_delays(mtask.delays)

                hints = session.query(SpearsHint).filter(SpearsHint.migration_task == mtask).all()
                bc.set_hints(hints)

                bc.save()

        if update_britney:
            log.info('Updating Britney')
            self._britney.update_dist()

        return True

    @concurrent.thread  # type: ignore[arg-type]
    def _write_merged_dists_data_for(
        self, session, mi_wspace: str, mtask: SpearsMigrationTask, suites: T.Union[ArchiveSuite, list[ArchiveSuite]]
    ):
        """Merge multiple suites into one new dummy suite, and combine arch:all and arch:any binary files."""

        suites = listify(suites)

        repo_root_dir = mtask.repo.get_root_dir()
        fake_dists_dir = self._get_suites_dists_staging_dir(mi_wspace, suites)

        for component in mtask.target_suite.components:
            for arch in mtask.target_suite.architectures:
                if arch.name == 'all':
                    continue
                packages_files: list[tuple[T.PathUnion, T.PathUnion]] = []

                for installer_dir in ['', 'debian-installer']:
                    for suite in suites:
                        pfile = os.path.join(
                            repo_root_dir,
                            'dists',
                            suite.name,
                            component.name,
                            installer_dir,
                            'binary-{}'.format(arch.name),
                            'Packages.xz',
                        )
                        pfile_all = os.path.join(
                            repo_root_dir,
                            'dists',
                            suite.name,
                            component.name,
                            installer_dir,
                            'binary-all',
                            'Packages.xz',
                        )
                        if os.path.isfile(pfile):
                            log.debug('Looking for packages in: {}'.format(pfile))
                            packages_files.append((pfile, pfile_all if os.path.isfile(pfile_all) else None))

                    if not installer_dir and not packages_files:
                        raise Exception(
                            'No packages found for {}/{}/{} in repo metadata for migration "{}:{}": Can not continue.'.format(
                                '+'.join([s.name for s in suites]),
                                component.name,
                                arch.name,
                                mtask.repo.name,
                                mtask.make_migration_shortname(),
                            )
                        )

                    # create new merged Packages file
                    target_packages_file = os.path.join(
                        fake_dists_dir, component.name, installer_dir, 'binary-{}'.format(arch.name), 'Packages.gz'
                    )
                    log.debug('Generating combined packages input file: {}'.format(target_packages_file))
                    os.makedirs(os.path.dirname(target_packages_file), exist_ok=True)

                    data = b''
                    for fname, fname_all in packages_files:
                        with open_compressed(fname) as f:
                            data += f.read()
                        if fname_all:
                            if data.rstrip():
                                data += b'\n'
                            with open_compressed(fname_all) as f:
                                data += f.read()
                        if data.rstrip():
                            data += b'\n'
                    with gzip.open(target_packages_file, 'w') as f:
                        f.write(data)

            sources_files = []
            for suite in suites:
                sfile = os.path.join(repo_root_dir, 'dists', suite.name, component.name, 'source', 'Sources.xz')
                if os.path.isfile(sfile):
                    log.debug('Looking for source packages in: {}'.format(sfile))
                    sources_files.append(sfile)

            if not sources_files:
                raise Exception(
                    'No packages found in "{}/{}" sources for migration "{}": Can not continue.'.format(
                        '+'.join([s.name for s in suites]), component.name, mtask.make_migration_shortname()
                    )
                )

            # Create new merged Sources file
            target_sources_file = os.path.join(fake_dists_dir, component.name, 'source', 'Sources.gz')
            log.debug('Generating combined sources input file: {}'.format(target_sources_file))
            os.makedirs(os.path.dirname(target_sources_file), exist_ok=True)

            data = b''
            for fname in sources_files:
                with open_compressed(fname) as f:
                    data += f.read()
                if data.rstrip():
                    data += b'\n'
            with gzip.open(target_sources_file, 'w') as f:
                f.write(data)

        # Britney needs a Release file to determine the source suites components and architectures.
        # To keep things simple, we just copy one of the source Release files.
        # TODO: Synthesize a dedicated file instead and be less lazy
        release_file = os.path.join(repo_root_dir, 'dists', suites[0].name, 'Release')
        target_release_file = os.path.join(fake_dists_dir, 'Release')
        log.debug('Using Release file for merged source suite: {}'.format(target_release_file))
        if os.path.isfile(target_release_file):
            os.remove(target_release_file)
        shutil.copyfile(release_file, target_release_file)

    def _prepare_source_dists_data(self, session, mi_wspace: str, mtask: SpearsMigrationTask) -> None:
        """
        If there is more than one source suite, we need to give Britney an amalgamation
        of the data of the two source suites.
        If there is only one suite, we need to merge arch:all into the native architecture file,
        as Britney does not work well with Laniakea's split-arch-all configuration (yet).

        This function prepares the combined data in the respective workspace location.
        """

        srcmerge_future = self._write_merged_dists_data_for(session, mi_wspace, mtask, mtask.source_suites)  # type: ignore[call-arg]
        dstmerge_future = self._write_merged_dists_data_for(session, mi_wspace, mtask, mtask.target_suite)  # type: ignore[call-arg]

        srcmerge_future.result()
        dstmerge_future.result()

    def _create_faux_packages(self, session, mi_wspace: str, mtask: SpearsMigrationTask) -> None:
        """
        If we have a partial source and target suite, we need to let Britney know about the
        parent packages somehow.
        At the moment, we simply abuse the FauxPackages system for that.
        """

        # we don't support more than one source suite for this feature at the moment
        if len(mtask.source_suites) > 1:
            log.info('Not auto-generating faux packages: Multiple suites set as sources.')
            return

        suite_source = mtask.source_suites[0]

        if suite_source.parents or mtask.target_suite.parents:
            log.info('Creating faux-packages to aid resolving of partial suites.')
        else:
            log.info('No auto-generating faux packages: No source and target suite parents, generation is unnecessary.')
            return

        existing_pkg_arch_set = set()
        log.debug('Creating index of valid packages that do not need a faux package.')

        # we need repository information to only generate faux packages if a package doesn't exist
        # in our source suite(s) already
        archive_root_dir = os.path.join(self._lconf.archive_root_dir, mtask.repo.name)
        repo_reader = RepositoryReader(archive_root_dir, mtask.repo.name, trusted_keyrings=[])
        repo_reader.set_trusted(True)  # we assume the local repository data is trusted
        for suite in mtask.source_suites:
            suite_nodb = ArchiveSuite(suite.name, suite.alias)
            for component in suite.components:
                component_nodb = ArchiveComponent(component.name)
                for arch in suite.architectures:
                    aname = arch.name
                    # create detached entities so the local packages aren't accidentally added to the database
                    arch_nodb = ArchiveArchitecture(arch.name)

                    # fetch package information
                    for bpkg in repo_reader.binary_packages(suite_nodb, component_nodb, arch_nodb):
                        existing_pkg_arch_set.add(aname + ':' + bpkg.name)
                    for spkg in repo_reader.source_packages(suite_nodb, component_nodb):
                        existing_pkg_arch_set.add(aname + ':' + spkg.name)
        del repo_reader

        log.debug('Generating faux packages list')
        fauxpkg_fname = os.path.join(mi_wspace, 'input', 'faux-packages')
        fauxpkg_data = {}

        for parent in mtask.target_suite.parents:
            for component in parent.components:
                for installer_dir in ['', 'debian-installer']:
                    for arch in parent.architectures:
                        pfile = os.path.join(
                            archive_root_dir,
                            'dists',
                            parent.name,
                            component.name,
                            installer_dir,
                            'binary-{}'.format(arch.name),
                            'Packages.xz',
                        )
                        if not os.path.isfile(pfile):
                            continue

                        log.debug('Reading data for faux packages list: {}'.format(pfile))

                        with TagFile(pfile) as tf:
                            for e in tf:
                                pkgname = e['Package']
                                pkgversion = e['Version']
                                pkgarch = e['Architecture']

                                pkid = '{}-{}-{}'.format(pkgname, pkgversion, pkgarch)
                                if pkid in fauxpkg_data:
                                    continue
                                pkgname_arch = pkgarch + ':' + pkgname
                                if pkgname_arch in existing_pkg_arch_set:
                                    continue
                                provides = e.get('Provides', '')

                                data = 'Package: {}\nVersion: {}'.format(pkgname, pkgversion)
                                if pkgarch and pkgarch != 'all':
                                    data = data + '\nArchitecture: {}'.format(pkgarch)
                                if provides:
                                    data = data + '\nProvides: {}'.format(provides)
                                if component.name != 'main':
                                    data = data + '\nComponent: {}'.format(component.name)

                                fauxpkg_data[pkid] = data

                                # FIXME: We shouldn't have to special-case this :any case,
                                # rather Britney should do the right thing and recognize this
                                # notation for faux-packages. But until that is fixed
                                # properly and since a dependency on python3:any is so common, we
                                # will work around this issue
                                if pkgname == 'python3':
                                    pkid = '{}-{}-{}'.format('python3:any', pkgversion, pkgarch)
                                    if pkid in fauxpkg_data:
                                        continue
                                    fauxpkg_data[pkid] = data.replace('Package: python3\n', 'Package: python3:any\n')

        with open(fauxpkg_fname, 'w') as f:
            for segment in fauxpkg_data.values():
                f.write(segment + '\n\n')

    def _collect_urgencies(self, session, mi_wspace: T.PathUnion, mtask: SpearsMigrationTask):
        log.debug('Collecting urgencies for %s:%s', mtask.repo.name, mtask.target_suite.name)
        udata = (
            session.query(SourcePackage.name, SourcePackage.version, SourcePackage.changes_urgency).filter(
                SourcePackage.repo_id == mtask.repo.id,
                SourcePackage.suites.any(id=mtask.target_suite_id),
                SourcePackage.time_deleted.is_(None),
            )
        ).all()

        log.info('Writing urgency policy file for: %s:%s', mtask.repo.name, mtask.target_suite.name)
        urgency_policy_file = os.path.join(mi_wspace, 'state', 'age-policy-urgencies')
        with open(urgency_policy_file, 'w') as f:
            for pkgname, version, changes_urgency in udata:
                f.write('{} {} {}\n'.format(pkgname, version, changes_urgency.to_string()))

    def _setup_dates(self, mi_wspace: T.PathUnion):
        dates_policy_file = os.path.join(mi_wspace, 'state', 'age-policy-dates')
        if os.path.isfile(dates_policy_file):
            return

        log.info('Writing dates policy file.')
        # just make an empty file for now
        with open(dates_policy_file, 'w') as f:
            f.write('\n')

    def _setup_various(self, mi_wspace: str, mtask: SpearsMigrationTask):
        # set up some random files which we do not use at all currently
        for suite in mtask.source_suites:
            rcbugs_policy_file_u = os.path.join(mi_wspace, 'state', 'rc-bugs-{}'.format(suite.name))
            if not os.path.isfile(rcbugs_policy_file_u):
                log.info('Writing RC bugs policy file (source).')
                # just make an empty file for now
                with open(rcbugs_policy_file_u, 'w') as f:
                    f.write('')

        rcbugs_policy_file_t = os.path.join(mi_wspace, 'state', 'rc-bugs-{}'.format(mtask.target_suite.name))
        if not os.path.isfile(rcbugs_policy_file_t):
            log.info('Writing RC bugs policy file (target).')
            # just make an empty file for now
            with open(rcbugs_policy_file_t, 'w') as f:
                f.write('')

        # there is no support for Piuparts yet, but Britney crashes without these files
        piupats_dummy_json = '{"_id": "Piuparts Package Test Results Summary", "_version": "1.0", "packages": {}}\n'
        for suite in mtask.source_suites:
            piuparts_file_u = os.path.join(mi_wspace, 'state', 'piuparts-summary-{}.json'.format(suite.name))
            if not os.path.isfile(piuparts_file_u):
                log.info('Writing Piuparts summary file (source).')
                # just make an empty file for now
                with open(piuparts_file_u, 'w') as f:
                    f.write(piupats_dummy_json)

        piuparts_file_t = os.path.join(mi_wspace, 'state', 'piuparts-summary-{}.json'.format(mtask.target_suite.name))
        if not os.path.isfile(piuparts_file_t):
            log.info('Writing Piuparts summary file (target).')
            # just make an empty file for now
            with open(piuparts_file_t, 'w') as f:
                f.write(piupats_dummy_json)

    def _postprocess_heidi_file(self, mi_wspace: str):
        heidi_result = os.path.join(mi_wspace, 'output', 'target', 'HeidiResult')
        processed_result = os.path.join(mi_wspace, 'output', 'target', 'heidi', 'current')

        final_data = []
        with open(heidi_result, 'r') as f:
            for line in f:
                parts = line.strip().split(' ')
                if len(parts) != 4:
                    log.warning('Found invalid line in Britney result: {}'.format(line.strip()))
                    continue
                final_data.append('{} {} {}'.format(parts[0], parts[1], parts[2]))

        os.makedirs(os.path.dirname(processed_result), exist_ok=True)
        with open(processed_result, 'w') as f:
            f.write('\n'.join(final_data))
            f.write('\n')

        return processed_result

    def _retrieve_excuses(self, session, mi_wspace: str, mtask: SpearsMigrationTask):
        excuses_yaml = os.path.join(mi_wspace, 'output', 'target', 'excuses.yaml')
        log_file = os.path.join(mi_wspace, 'output', 'target', 'output.txt')

        if not os.path.isfile(excuses_yaml) or not os.path.isfile(log_file):
            raise Exception('Unable to find and process the excuses information. Spears data will be outdated.')

        efile = ExcusesFile(session, excuses_yaml, log_file, mtask)
        excuses = []
        for _, excuse in efile.get_excuses().items():
            if excuse in session:
                session.expunge(excuse)  # don't add this to the database yet
            excuses.append(excuse)

        return excuses

    def _run_migration_internal(self, session, mtask: SpearsMigrationTask):
        mi_wspace = self._get_migrate_workspace(mtask)
        britney_conf = os.path.join(mi_wspace, 'britney.conf')
        migration_displayname = self._get_migration_displayname(mtask.repo, mtask.source_suites, mtask.target_suite)
        if not os.path.isfile(britney_conf):
            log.warning(
                'No Britney config for migration run "{}" - maybe the configuration was not yet updated?'.format(
                    migration_displayname
                )
            )
            return None

        log.info('Migration run for "{}"'.format(migration_displayname))
        # ensure prerequisites are met and Britney is fed with all the data it needs
        self._prepare_source_dists_data(session, mi_wspace, mtask)
        self._create_faux_packages(session, mi_wspace, mtask)
        self._collect_urgencies(session, mi_wspace, mtask)
        self._setup_dates(mi_wspace)
        self._setup_various(mi_wspace, mtask)

        # execute the migration tester
        log.info('Running Britney (%s)', migration_displayname)
        self._britney.run(mi_wspace, britney_conf)

        # prepare result for import
        log.info('Reading result')
        heidi_result = self._postprocess_heidi_file(mi_wspace)

        # tell lk-archive to import the new data (overriding the target suite)
        log.info('Importing changed data (%s)', migration_displayname)
        proc = subprocess.run(
            [
                self._lk_archive_exe,
                'import-heidi',
                '--repo',
                mtask.repo.name,
                '-s',
                mtask.target_suite.name,
                '--with-rm',
                heidi_result,
            ],
            check=True,
        )
        if proc.returncode != 0:
            return None

        log.info('Retrieving excuses (%s)', migration_displayname)
        res = self._retrieve_excuses(session, mi_wspace, mtask)
        return res

    def _run_migration_for_entries(self, session, migration_tasks: T.List[SpearsMigrationTask]):
        # event emitted for message publishing
        emitter = EventEmitter(LkModule.SPEARS)

        for mtask in migration_tasks:
            print(
                '\nRunning migration: {} to {}\n'.format(
                    '+'.join([s.name for s in mtask.source_suites]), mtask.target_suite.name
                )
            )
            assert len(mtask.source_suites) >= 1

            n_excuses = self._run_migration_internal(session, mtask)
            if n_excuses is None:
                continue

            # list existing excuses
            existing_excuses = {}
            all_excuses = session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == mtask.id).all()
            for excuse in all_excuses:
                existing_excuses[excuse.make_idname()] = excuse

            for new_excuse in n_excuses:
                excuse = existing_excuses.pop(new_excuse.make_idname(), None)
                if excuse:
                    # the excuse already exists, so we just update it
                    excuse_is_new = False
                else:
                    excuse_is_new = True
                    excuse = new_excuse

                if excuse_is_new:
                    excuse.uuid = uuid4()  # we need an UUID immediately to submit it in the event payload
                    session.add(excuse)

                    data = {
                        'uuid': str(excuse.uuid),
                        'suites_source': [s.name for s in excuse.migration_task.source_suites],
                        'suite_target': excuse.migration_task.target_suite.name,
                        'source_package': excuse.source_package.name,
                        'version_new': excuse.version_new,
                        'version_old': excuse.version_old,
                    }
                    emitter.submit_event('new-excuse', data)
                else:
                    excuse.is_candidate = new_excuse.is_candidate
                    excuse.maintainer = new_excuse.maintainer

                    excuse.age_current = new_excuse.age_current
                    excuse.age_required = new_excuse.age_required

                    excuse.missing_archs_primary = new_excuse.missing_archs_primary
                    excuse.missing_archs_secondary = new_excuse.missing_archs_secondary

                    excuse.set_old_binaries(new_excuse.get_old_binaries())

                    excuse.blocked_by = new_excuse.blocked_by
                    excuse.migrate_after = new_excuse.migrate_after
                    excuse.manual_block = new_excuse.manual_block
                    excuse.other = new_excuse.other
                    excuse.log_excerpt = new_excuse.log_excerpt

            for excuse in existing_excuses.values():
                data = {
                    'uuid': str(excuse.uuid),
                    'suites_source': [s.name for s in excuse.migration_task.source_suites],
                    'suite_target': excuse.migration_task.target_suite.name,
                    'source_package': excuse.source_package.name,
                    'version_new': excuse.version_new,
                    'version_old': excuse.version_old,
                }
                emitter.submit_event('excuse-removed', data)
                session.delete(excuse)

            # add changes to the database early
            session.commit()

        return True

    def run_migration(self, repo_name: str, source_suite_name: str, target_suite_name: str):
        with session_scope() as session:
            migration_tasks = session.query(SpearsMigrationTask).all()
            if source_suite_name:
                # we have parameters, so limit which migration entries we act on
                if not target_suite_name:
                    log.error('Target suite parameter is missing!')
                    return False

                source_suite_names = source_suite_name.split('+')
                migration_found = False
                for mtask in migration_tasks:
                    if mtask.repo.name != repo_name:
                        continue
                    if mtask.target_suite.name != target_suite_name:
                        continue
                    mtask_src_suite_names = [s.name for s in mtask.source_suites]
                    if sorted(mtask_src_suite_names) != sorted(source_suite_names):
                        continue
                    migration_found = True
                    migration_tasks = [mtask]
                    break

                if not migration_found:
                    log.error('Could not find migration recipe with the given parameters.')
                    return False

            return self._run_migration_for_entries(session, migration_tasks)
