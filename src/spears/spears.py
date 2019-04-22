#!/usr/bin/env python3
#
# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser
from laniakea.db import session_factory, SpearsMigrationEntry, SpearsHint, \
    SpearsExcuse, SpearsOldBinaries
from lknative import SpearsEngine


def get_spears_config():
    from lknative import SpearsHint as LknSpearsHint
    from lknative import SpearsConfig, SpearsConfigEntry, int_to_versionpriority
    from laniakea.lknative_utils import create_native_baseconfig, get_suiteinfo_all_suites
    from laniakea.localconfig import ExternalToolsUrls

    bconf = create_native_baseconfig()

    ext_urls = ExternalToolsUrls()
    sconf = SpearsConfig()
    sconf.britneyGitOriginUrl = ext_urls.britney_git_repository

    session = session_factory()
    migration_entries = session.query(SpearsMigrationEntry).all()
    mdict = {}
    for entry in migration_entries:
        centry = SpearsConfigEntry()
        centry.sourceSuites = entry.source_suites
        centry.targetSuite = entry.target_suite

        d = {}
        for k, v in entry.delays.items():
            d[int_to_versionpriority(int(k))] = int(v)
        centry.delays = d

        hints = session.query(SpearsHint).filter(SpearsHint.migration_id == entry.idname).all()
        chints = []
        for hint in hints:
            chint = LknSpearsHint()
            chint.hint = hint.hint
            chint.reason = hint.reason
            chint.date = hint.time
            chints.append(chint)
        centry.hints = chints

        mdict[entry.idname] = centry
    sconf.migrations = mdict

    suites = get_suiteinfo_all_suites()

    return bconf, sconf, suites


def command_update(options):
    ''' Update Britney and its configuration '''

    bconf, sconf, suites = get_spears_config()
    engine = SpearsEngine(bconf, sconf, suites)

    ret = engine.updateConfig()
    if not ret:
        sys.exit(2)


def command_migrate(options):
    ''' Run a Britney migration '''

    bconf, sconf, suites = get_spears_config()
    engine = SpearsEngine(bconf, sconf, suites)

    session = session_factory()

    excuses = []
    if options.suite1:
        if not options.suite2:
            print('Target suite parameter is missing!')
            sys.exit(1)

        ret, excuses = engine.runMigration(options.suite1, options.suite2)
        if not ret:
            sys.exit(2)

        # remove old excuses
        migration_id = '{}-to-{}'.format(options.suite1, options.suite2)
        session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == migration_id).delete()
    else:
        migration_entries = session.query(SpearsMigrationEntry).all()
        for entry in migration_entries:
            print('\nRunning migration: {} to {}\n'.format('+'.join(entry.source_suites), entry.target_suite))
            ret, tmp_excuses = engine.runMigration('+'.join(entry.source_suites), entry.target_suite)
            if not ret:
                sys.exit(2)
            excuses.extend(tmp_excuses)

        # remove old excuses
        for entry in migration_entries:
            session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == entry.make_migration_id()).delete()

    for ex in excuses:
        excuse = SpearsExcuse()

        #excuse.time = ex.date # noqa
        excuse.migration_id = ex.migrationId
        excuse.suite_source = ex.sourceSuite
        excuse.suite_target = ex.targetSuite

        excuse.is_candidate = ex.isCandidate

        excuse.source_package = ex.sourcePackage
        excuse.maintainer = ex.maintainer

        excuse.age_current = ex.age.currentAge
        excuse.age_required = ex.age.requiredAge

        excuse.version_new = ex.newVersion
        excuse.version_old = ex.oldVersion

        excuse.missing_archs_primary = ex.missingBuilds.primaryArchs
        excuse.missing_archs_secondary = ex.missingBuilds.secondaryArchs

        obins = []
        for ob in ex.oldBinaries:
            obin = SpearsOldBinaries()
            obin.pkg_version = ob.pkgVersion
            obin.binaries = ob.binaries
            obins.append(obin)
        excuse.set_old_binaries(obins)

        excuse.blocked_by = ex.reason.blockedBy
        excuse.migrate_after = ex.reason.migrateAfter
        excuse.manual_block = ex.reason.manualBlock
        excuse.other = ex.reason.other
        excuse.log_excerpt = ex.reason.logExcerpt

        session.add(excuse)

    session.commit()


def create_parser(formatter_class=None):
    ''' Create Spears CLI argument parser '''

    parser = ArgumentParser(description='Migrate packages between suites')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('update', help='Update the copy of Britney and its configuration.')
    sp.set_defaults(func=command_update)

    sp = subparsers.add_parser('migrate', help='Run migration. If suites are omitted, migration is run for all targets.')
    sp.add_argument('suite1', type=str, help='The first suite.', nargs='?')
    sp.add_argument('suite2', type=str, help='The second suite.', nargs='?')
    sp.set_defaults(func=command_migrate)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
