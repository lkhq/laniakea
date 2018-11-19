#!/usr/bin/env python3

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser
from laniakea import LocalConfig, LkModule
from laniakea.db import config_get_value, session_factory, ArchiveSuite, \
    SyncBlacklistEntry, SynchrotronIssue, SynchrotronIssueKind
from lknative import BaseConfig, SynchrotronConfig, SyncEngine


def get_sync_config():
    from lknative import SyncSourceSuite
    from laniakea.lknative_utils import create_native_baseconfig

    lconf = LocalConfig()
    bconf = create_native_baseconfig()

    sconf = SynchrotronConfig()
    sconf.sourceName = config_get_value(LkModule.SYNCHROTRON, 'source_name')
    sconf.syncEnabled = True if config_get_value(LkModule.SYNCHROTRON, 'sync_enabled') else False
    sconf.syncBinaries = True if config_get_value(LkModule.SYNCHROTRON, 'sync_binaries') else False
    sconf.sourceKeyrings = lconf.synchrotron_sourcekeyrings

    sconf.source.defaultSuite = config_get_value(LkModule.SYNCHROTRON, 'source_default_suite')
    sconf.source.repoUrl = config_get_value(LkModule.SYNCHROTRON, 'source_repo_url')
    suites_list = config_get_value(LkModule.SYNCHROTRON, 'source_suites')
    if not suites_list:
        suites_list = []
    source_suites = []
    for sd in suites_list:
        sssuite = SyncSourceSuite()
        sssuite.name = sd['name']
        sssuite.architectures = sd['architectures']
        sssuite.components = sd['components']

        source_suites.append(sssuite)
    sconf.source.suites = source_suites

    return bconf, sconf


def get_incoming_suite_info():
    from lknative import SuiteInfo

    session = session_factory()
    si = SuiteInfo()

    # FIXME: We need much better ways to select the right suite to synchronize with
    suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.accept_uploads==True).one()
    si.name = suite.name
    si.architectures = list(a.name for a in suite.architectures)
    si.components = list(c.name for c in suite.components)

    return si


def get_package_blacklist():
    session = session_factory()

    pkgnames = [value for value, in session.query(SyncBlacklistEntry.pkgname)]
    return pkgnames


def command_sync(options):
    ''' Synchronize a dedicated set of packages '''

    if not options.packages:
        print('You need to define at least one package to synchronize!')
        sys.exit(1)

    bconf, sconf = get_sync_config()
    incoming_suite = get_incoming_suite_info()
    engine = SyncEngine(bconf, sconf, incoming_suite)

    blacklist_pkgnames = get_package_blacklist()
    engine.setSourceSuite(options.source_suite)
    engine.setBlacklist(blacklist_pkgnames)

    ret = engine.syncPackages (options.component, options.packages, options.force)
    if not ret:
        sys.exit(2)


def command_autosync(options):
    ''' Automatically synchronize packages '''

    bconf, sconf = get_sync_config()
    incoming_suite = get_incoming_suite_info()
    engine = SyncEngine(bconf, sconf, incoming_suite)

    blacklist_pkgnames = get_package_blacklist()
    engine.setBlacklist(blacklist_pkgnames)

    ret, issue_data = engine.autosync()
    if not ret:
        sys.exit(2)
        return

    session = session_factory()
    for ssuite in sconf.source.suites:
        session.query(SynchrotronIssue).filter(SynchrotronIssue.source_suite==ssuite.name, \
            SynchrotronIssue.target_suite==incoming_suite.name).delete()

    for info in issue_data:
        issue = SynchrotronIssue()
        issue.kind = SynchrotronIssueKind(info.kind)
        issue.package_name = info.packageName
        issue.source_suite = info.sourceSuite
        issue.target_suite = info.targetSuite
        issue.source_version = info.sourceVersion
        issue.target_version = info.targetVersion
        issue.details = info.details
        session.add(issue)
    session.commit()


def create_parser(formatter_class=None):
    ''' Create synchrotron CLI argument parser '''

    parser = ArgumentParser(description='Synchronize packages with another distribution')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of debspawn itself.')

    sp = subparsers.add_parser('sync', help='Synchronize a package or set of packages')
    sp.add_argument('--force', action='store_true', dest='force', help='Force package import and ignore version conflicts.')
    sp.add_argument('source_suite', type=str, help='The suite to synchronize from')
    sp.add_argument('component', type=str, help='The archive component to import from')
    sp.add_argument('packages', nargs='+', help='The (source) packages to import')
    sp.set_defaults(func=command_sync)

    sp = subparsers.add_parser('autosync', help='Synchronize a package or set of packages')
    sp.set_defaults(func=command_autosync)

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
