# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from __future__ import annotations

import os
import lzma
import shutil
from uuid import uuid4
from typing import Any

from apt_pkg import TagFile
from sqlalchemy.orm import joinedload

from laniakea.db import (
    LkModule,
    SpearsHint,
    ArchiveSuite,
    SpearsExcuse,
    ArchiveRepository,
    SpearsMigrationEntry,
    session_scope,
)
from laniakea.utils import open_compressed
from laniakea.logging import log
from laniakea.dakbridge import DakBridge
from laniakea.msgstream import EventEmitter
from laniakea.repository import Repository
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

    def _get_source_suite_dists_dir(self, mi_workspace: str, source_suites: list[ArchiveSuite]):
        '''
        If our source suite is a single suite, we can just use the archive's vanilla dists/
        directory as source of package information for Britney.
        If we use Britney to migrate packages from two suites together however, we need
        an amalgamation of the two suites' Packages/Sources files, which resides in Britney's
        workspace directory.
        This function returns the correct dists/ path, depending on the case.
        '''

        if not source_suites:
            raise Exception('Can not get source-suite dists/ directory if no source suites are selected.')

        if len(source_suites) == 1:
            return os.path.join(self._lconf.archive_root_dir, 'dists', source_suites[0].name)

        dists_dir = os.path.join(mi_workspace, 'input', 'dists', '+'.join([s.name for s in source_suites]))
        os.makedirs(dists_dir, exist_ok=True)
        return dists_dir

    def _suites_from_migration_entry(self, session, mentry: SpearsMigrationEntry):

        res: dict[str, Any] = {'error': False, 'from': [], 'to': None}

        for suite_name in mentry.source_suites:
            maybe_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one_or_none()
            if not maybe_suite:
                log.error(
                    'Migration source suite "{}" does not exist. Can not create configuration.'.format(suite_name)
                )
                res['error'] = True
                return res
            res['from'].append(maybe_suite)

        maybe_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == mentry.target_suite).one_or_none()
        if not maybe_suite:
            log.error(
                'Migration target suite "{}" does not exist. Can not create configuration.'.format(mentry.target_suite)
            )
            res['error'] = True
            return res
        res['to'] = maybe_suite

        if res['to'] in res['from']:
            log.error('Migration target suite ({}) is contained in source suite list.'.format(res['to'].name))
            res['error'] = True
            return res

        return res

    def _get_migration_id(self, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite) -> str:
        return '{}-to-{}'.format('+'.join(sorted([s.name for s in suites_from])), suite_to.name)

    def _get_migration_name(self, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite) -> str:
        return '{} -> {}'.format('+'.join(sorted([s.name for s in suites_from])), suite_to.name)

    def _get_migrate_workspace(self, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite) -> str:
        return os.path.join(self._workspace, self._get_migration_id(suites_from, suite_to))

    def _get_local_repo(self, session, repo_name='master'):
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()
        local_repo = Repository(self._lconf.archive_root_dir, repo.name, trusted_keyrings=[])

        # we unconditionally trust the local repository - for now
        local_repo.set_trusted(True)
        return local_repo

    def update_config(self):
        '''
        Update configuration and distribution
        copy of Britney
        '''

        log.info('Updating configuration')

        with session_scope() as session:
            for mentry in session.query(SpearsMigrationEntry).all():

                si_res = self._suites_from_migration_entry(session, mentry)
                if si_res['error']:
                    continue
                suites_from = si_res['from']
                suite_to = si_res['to']
                assert len(suites_from) >= 1

                log.info('Refreshing Britney config for "{}"'.format(self._get_migration_name(suites_from, suite_to)))
                mi_wspace = self._get_migrate_workspace(suites_from, suite_to)
                bc = BritneyConfig(mi_wspace)
                bc.set_archive_paths(
                    self._get_source_suite_dists_dir(mi_wspace, suites_from),
                    os.path.join(self._lconf.archive_root_dir, 'dists', suite_to.name),
                )
                bc.set_components([c.name for c in suite_to.components])
                bc.set_architectures([a.name for a in suite_to.architectures])
                bc.set_delays(mentry.delays)

                hints = session.query(SpearsHint).filter(SpearsHint.migration_id == mentry.make_migration_id()).all()
                bc.set_hints(hints)

                bc.save()

        log.info('Updating Britney')
        self._britney.update_dist()

        return True

    def _prepare_source_data(
        self, session, mi_wspace: str, suites_source: list[ArchiveSuite], suite_target: ArchiveSuite
    ):
        '''
        If there is more than one source suite, we need to give Britney an amalgamation
        of the data of the two source suites.
        This function prepares this data.
        '''

        # only one suite means we can use the suite's data directly
        if len(suites_source) <= 1:
            return

        archive_root_dir = self._lconf.archive_root_dir
        fake_dists_dir = self._get_source_suite_dists_dir(mi_wspace, suites_source)

        for component in suite_target.components:
            for arch in suite_target.architectures:
                if arch.name == 'all':
                    continue
                packages_files = []

                for installer_dir in ['', 'debian-installer']:
                    for suite_source in suites_source:
                        pfile = os.path.join(
                            archive_root_dir,
                            'dists',
                            suite_source.name,
                            component.name,
                            installer_dir,
                            'binary-{}'.format(arch.name),
                            'Packages.xz',
                        )
                        if os.path.isfile(pfile):
                            log.debug('Looking for packages in: {}'.format(pfile))
                            packages_files.append(pfile)

                    if not installer_dir and not installer_dir:
                        raise Exception(
                            'No packages found on {}/{} in sources for migration "{}": Can not continue.'.format(
                                component.name, arch.name, self._get_migration_id(suites_source, suite_target)
                            )
                        )

                    # create new merged Packages file
                    target_packages_file = os.path.join(
                        fake_dists_dir, component.name, installer_dir, 'binary-{}'.format(arch.name), 'Packages.xz'
                    )
                    log.debug('Generating combined new fake packages file: {}'.format(target_packages_file))
                    os.makedirs(os.path.dirname(target_packages_file), exist_ok=True)

                    data = b''
                    for fname in packages_files:
                        with open_compressed(fname) as f:
                            data = data + f.read()
                    with lzma.open(target_packages_file, 'w') as f:
                        f.write(data)

            sources_files = []
            for suite_source in suites_source:
                sfile = os.path.join(
                    archive_root_dir, 'dists', suite_source.name, component.name, 'source', 'Sources.xz'
                )
                if os.path.isfile(sfile):
                    log.debug('Looking for source packages in: {}'.format(sfile))
                    sources_files.append(sfile)

            if not sources_files:
                raise Exception(
                    'No source packages found in "{}" sources for migration "{}": Can not continue.'.format(
                        component.name, self._get_migration_id(suites_source, suite_target)
                    )
                )

            # Create new merged Sources file
            target_sources_file = os.path.join(fake_dists_dir, component.name, 'source', 'Sources.xz')
            log.debug('Generating combined new fake sources file: {}'.format(target_sources_file))
            os.makedirs(os.path.dirname(target_sources_file), exist_ok=True)

            data = b''
            for fname in sources_files:
                with open_compressed(fname) as f:
                    data = data + f.read()
            with lzma.open(target_sources_file, 'w') as f:
                f.write(data)

        # Britney needs a Release file to determine the source suites components and architectures.
        # To keep things simple, we just copy one of the source Release files.
        # TODO: Synthesize a dedicated file instead and be less lazy
        release_file = os.path.join(archive_root_dir, 'dists', suites_source[0].name, 'Release')
        target_release_file = os.path.join(fake_dists_dir, 'Release')
        log.debug('Using Release file for fake suite: {}'.format(target_release_file))
        if os.path.join(target_release_file):
            os.remove(target_release_file)
        shutil.copyfile(release_file, target_release_file)

    def _create_faux_packages(
        self, session, mi_wspace: str, suites_source: list[ArchiveSuite], suite_target: ArchiveSuite
    ):
        '''
        If we have a partial source and target suite, we need to let Britney know about the
        parent packages somehow.
        At the moment, we simply abuse the FauxPackages system for that.
        '''

        # we don't support more than one source suite for this feature at the moment
        if len(suites_source) > 1:
            log.info('Not auto-generating faux packages: Multiple suites set as sources.')
            return

        suite_source = suites_source[0]

        if suite_source.parent and suite_target.parent:
            log.info('Creating faux-packages to aid resolving of partial suites.')
        else:
            log.info('No auto-generating faux packages: No source and target suite parents, generation is unnecessary.')
            return

        existing_pkg_arch_set = set()
        log.debug('Creating index of valid packages that do not need a faux package.')

        # we need repository information to only generate faux packages if a package doesn't exist
        # in our source suite(s) already
        repo = self._get_local_repo(session)

        for suite in suites_source:
            esuite = (
                session.query(ArchiveSuite)
                .options(joinedload(ArchiveSuite.components))
                .options(joinedload(ArchiveSuite.architectures))
                .filter(ArchiveSuite.id == suite.id)
                .one()
            )
            session.expunge(esuite)  # we don't want packages accidentally added to the database here
            for component in esuite.components:
                for arch in esuite.architectures:
                    aname = arch.name
                    for bpkg in repo.binary_packages(esuite, component, arch):
                        existing_pkg_arch_set.add(aname + ':' + bpkg.name)
                    for spkg in repo.source_packages(esuite, component):
                        existing_pkg_arch_set.add(aname + ':' + spkg.name)

        archive_root_dir = self._lconf.archive_root_dir
        fauxpkg_fname = os.path.join(mi_wspace, 'input', 'faux-packages')

        log.debug('Generating faux packages list')
        fauxpkg_data = {}
        for component in suite_target.parent.components:

            for installer_dir in ['', 'debian-installer']:
                for arch in suite_target.parent.architectures:
                    pfile = os.path.join(
                        archive_root_dir,
                        'dists',
                        suite_target.parent.name,
                        component.name,
                        installer_dir,
                        'binary-{}'.format(arch.name),
                        'Packages.xz',
                    )
                    if not os.path.isfile(pfile):
                        continue

                    log.debug('Reading data for faux packages list: {}'.format(pfile))

                    with TagFile(pfile) as tf:  # type: ignore[attr-defined]
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

    def _collect_urgencies(self, mi_wspace: str):

        urgencies = ''
        for subdir, dirs, files in os.walk(self._lconf.archive_urgencies_export_dir):
            for fbasename in files:
                fname = os.path.join(subdir, fbasename)
                if not os.path.isfile(fname):
                    continue
                if not fbasename.startswith('install-urgencies'):
                    continue

                log.debug('Reading urgencies from {}'.format(fname))
                with open(fname, 'r') as f:
                    urgencies = urgencies + f.read()

        log.info('Writing urgency policy file.')
        urgency_policy_file = os.path.join(mi_wspace, 'state', 'age-policy-urgencies')
        with open(urgency_policy_file, 'w') as f:
            f.write(urgencies)

    def _setup_dates(self, mi_wspace: str):
        dates_policy_file = os.path.join(mi_wspace, 'state', 'age-policy-dates')
        if os.path.isfile(dates_policy_file):
            return

        log.info('Writing dates policy file.')
        # just make an empty file for now
        with open(dates_policy_file, 'w') as f:
            f.write('\n')

    def _setup_various(self, mi_wspace: str, suites_source: list[ArchiveSuite], suite_target: ArchiveSuite):
        # set up some random files which we do not use at all currently
        for suite in suites_source:
            rcbugs_policy_file_u = os.path.join(mi_wspace, 'state', 'rc-bugs-{}'.format(suite.name))
            if not os.path.isfile(rcbugs_policy_file_u):
                log.info('Writing RC bugs policy file (source).')
                # just make an empty file for now
                with open(rcbugs_policy_file_u, 'w') as f:
                    f.write('')

        rcbugs_policy_file_t = os.path.join(mi_wspace, 'state', 'rc-bugs-{}'.format(suite_target.name))
        if not os.path.isfile(rcbugs_policy_file_t):
            log.info('Writing RC bugs policy file (target).')
            # just make an empty file for now
            with open(rcbugs_policy_file_t, 'w') as f:
                f.write('')

        # there is no support for Piuparts yet, but Britney crashes without these files
        piupats_dummy_json = '{"_id": "Piuparts Package Test Results Summary", "_version": "1.0", "packages": {}}\n'
        for suite in suites_source:
            piuparts_file_u = os.path.join(mi_wspace, 'state', 'piuparts-summary-{}.json'.format(suite.name))
            if not os.path.isfile(piuparts_file_u):
                log.info('Writing Piuparts summary file (source).')
                # just make an empty file for now
                with open(piuparts_file_u, 'w') as f:
                    f.write(piupats_dummy_json)

        piuparts_file_t = os.path.join(mi_wspace, 'state', 'piuparts-summary-{}.json'.format(suite_target.name))
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

    def _retrieve_excuses(self, session, mi_wspace: str, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite):

        excuses_yaml = os.path.join(mi_wspace, 'output', 'target', 'excuses.yaml')
        log_file = os.path.join(mi_wspace, 'output', 'target', 'output.txt')

        if not os.path.isfile(excuses_yaml) or not os.path.isfile(log_file):
            raise Exception('Unable to find and process the excuses information. Spears data will be outdated.')

        if len(suites_from) <= 1:
            efile = ExcusesFile(excuses_yaml, log_file, suites_from[0].name, suite_to.name)
        else:
            efile = ExcusesFile(excuses_yaml, log_file, None, suite_to.name)

        # get a unique identifier for this migration task
        migration_id = self._get_migration_id(suites_from, suite_to)

        # read repository information to match packages to their source suites before adding
        # their excuses to the database.
        # This is only needed for multi-source-suite combined migrations, otherwise there is only one
        # source suites packages can originate from.
        pkg_source_suite_map = {}

        if len(suites_from) > 1:
            # we need repository information to attribute packages to their right suites
            repo = self._get_local_repo(session)

            for suite in suites_from:
                esuite = (
                    session.query(ArchiveSuite)
                    .options(joinedload(ArchiveSuite.components))
                    .options(joinedload(ArchiveSuite.architectures))
                    .filter(ArchiveSuite.id == suite.id)
                    .one()
                )
                session.expunge(esuite)  # we don't want packages accidentally added to the database here
                for component in esuite.components:
                    for spkg in repo.source_packages(esuite, component):
                        pkg_source_suite_map[spkg.name + '/' + spkg.version] = esuite.name

        excuses = []
        for _, excuse in efile.get_excuses().items():
            pkid = excuse.source_package + '/' + excuse.version_new
            suite_name = pkg_source_suite_map.get(pkid)
            if suite_name:
                excuse.suite_source = suite_name
            excuse.migration_id = migration_id
            excuses.append(excuse)

        return excuses

    def _run_migration_internal(self, session, suites_from: list[ArchiveSuite], suite_to: ArchiveSuite):

        mi_wspace = self._get_migrate_workspace(suites_from, suite_to)
        britney_conf = os.path.join(mi_wspace, 'britney.conf')
        if not os.path.isfile(britney_conf):
            log.warning(
                'No Britney config for migration run "{}" - maybe the configuration was not yet updated?'.format(
                    self._get_migration_name(suites_from, suite_to)
                )
            )
            return None

        log.info('Migration run for "{}"'.format(self._get_migration_name(suites_from, suite_to)))
        # ensure prerequisites are met and Britney is fed with all the data it needs
        self._prepare_source_data(session, mi_wspace, suites_from, suite_to)
        self._create_faux_packages(session, mi_wspace, suites_from, suite_to)
        self._collect_urgencies(mi_wspace)
        self._setup_dates(mi_wspace)
        self._setup_various(mi_wspace, suites_from, suite_to)

        # execute the migration tester
        self._britney.run(mi_wspace, britney_conf)

        # tell dak to import the new data (overriding the target suite)
        dak = DakBridge()
        heidi_result = self._postprocess_heidi_file(mi_wspace)
        ret = dak.set_suite_to_britney_result(suite_to.name, heidi_result)
        if not ret:
            return None

        res = self._retrieve_excuses(session, mi_wspace, suites_from, suite_to)
        return res

    def _run_migration_for_entries(self, session, migration_entries):

        # event emitted for message publishing
        emitter = EventEmitter(LkModule.SPEARS)

        for mentry in migration_entries:
            si_res = self._suites_from_migration_entry(session, mentry)
            if si_res['error']:
                continue
            print('\nRunning migration: {} to {}\n'.format('+'.join(mentry.source_suites), mentry.target_suite))
            suites_from = si_res['from']
            suite_to = si_res['to']
            assert len(suites_from) >= 1

            n_excuses = self._run_migration_internal(session, suites_from, suite_to)
            if n_excuses is None:
                continue

            migration_id = mentry.make_migration_id()

            # list existing excuses
            existing_excuses = {}
            all_excuses = session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == migration_id).all()
            for excuse in all_excuses:
                eid = '{}-{}:{}-{}/{}'.format(
                    excuse.suite_source,
                    excuse.suite_target,
                    excuse.source_package,
                    excuse.version_new,
                    excuse.version_old,
                )
                existing_excuses[eid] = excuse

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
                        'suite_source': excuse.suite_source,
                        'suite_target': excuse.suite_target,
                        'source_package': excuse.source_package,
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
                    'suite_source': excuse.suite_source,
                    'suite_target': excuse.suite_target,
                    'source_package': excuse.source_package,
                    'version_new': excuse.version_new,
                    'version_old': excuse.version_old,
                }
                emitter.submit_event('excuse-removed', data)
                session.delete(excuse)

            # add changes to the database early
            session.commit()

        return True

    def run_migration(self, source_suite_name: str, target_suite_name: str):

        with session_scope() as session:
            migration_entries = session.query(SpearsMigrationEntry).all()
            if source_suite_name:
                # we have parameters, so limit which migration entries we act on
                if not target_suite_name:
                    log.error('Target suite parameter is missing!')
                    return False

                migration_found = False
                migration_id = '{}-to-{}'.format(source_suite_name, target_suite_name)
                for entry in migration_entries:
                    if entry.make_migration_id() == migration_id:
                        migration_found = True
                        migration_entries = [entry]
                        break

                if not migration_found:
                    log.error('Could not find migration recipe with ID "{}"'.format(migration_id))
                    return False

            return self._run_migration_for_entries(session, migration_entries)
