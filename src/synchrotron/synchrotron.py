#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', 'lib', 'laniakea')))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', 'lib', 'laniakea', 'laniakea')))
if not thisfile.startswith(('/usr', '/bin')):
    sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))
    sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', 'laniakea')))

from argparse import ArgumentParser
from laniakea import LocalConfig, LkModule
from laniakea.db import session_scope, SynchrotronSource, SynchrotronConfig, SyncBlacklistEntry, \
    ArchiveSuite, SynchrotronIssue, SynchrotronIssueKind
from laniakea.native import SyncEngine, get_suiteinfo_for_suite
from laniakea.logging import log
from laniakea.msgstream import EventEmitter


def get_sync_config():
    import laniakea.native
    from laniakea.native import SyncSourceSuite, create_native_baseconfig

    lconf = LocalConfig()
    bconf = create_native_baseconfig()

    with session_scope() as session:
        sync_sources = session.query(SynchrotronSource).all()

        # FIXME: SynchrotronConfig needs adjustments in the D code to work
        # better with the new "multiple autosync tasks" model.
        # Maybe when doing this there's a good opportunity to rewrite some of
        # the D code in Python...
        sconf = laniakea.native.SynchrotronConfig()
        sconf.sourceName = sync_sources[0].os_name
        sconf.syncBinaries = False
        sconf.sourceKeyrings = lconf.synchrotron_sourcekeyrings

        sconf.source.defaultSuite = None
        sconf.source.repoUrl = sync_sources[0].repo_url

        source_suites = []
        for sd in sync_sources:
            sssuite = SyncSourceSuite()
            sssuite.name = sd.suite_name
            sssuite.architectures = sd.architectures
            sssuite.components = sd.components

            source_suites.append(sssuite)
        sconf.source.suites = source_suites

    return bconf, sconf


def get_package_blacklist():
    with session_scope() as session:
        pkgnames = [value for value, in session.query(SyncBlacklistEntry.pkgname)]
    return pkgnames


def publish_synced_spkg_events(engine, src_os, src_suite, dest_suite, forced=False, emitter=None):
    ''' Submit events for the synced source packages to the message stream '''
    if not emitter:
        emitter = EventEmitter(LkModule.SYNCHROTRON)
    spkgs = engine.getSyncedSourcePackages()
    for spkg in spkgs:
        data = {'name': spkg.name,
                'version': spkg.ver,
                'src_os': src_os,
                'src_suite': src_suite,
                'dest_suite': dest_suite,
                'forced': forced}

        emitter.submit_event('src-package-imported', data)


def command_sync(options):
    ''' Synchronize a dedicated set of packages '''

    if not options.packages:
        print('You need to define at least one package to synchronize!')
        sys.exit(1)

    bconf, sconf = get_sync_config()

    with session_scope() as session:
        si = session.query(SynchrotronConfig) \
            .join(SynchrotronConfig.destination_suite) \
            .join(SynchrotronConfig.source) \
            .filter(ArchiveSuite.name == options.dest_suite,
                    SynchrotronSource.suite_name == options.src_suite).one_or_none()
        if not si:
            log.error('Unable to find a sync config for this source/destination combination.')
            sys.exit(4)
            return

        if not si.sync_enabled:
            log.error('Can not synchronize package: Synchronization is disabled for this configuration.')
            sys.exit(3)
            return

        incoming_suite = get_suiteinfo_for_suite(si.destination_suite)
        sconf.syncBinaries = si.sync_binaries
        sconf.source.defaultSuite = si.source.suite_name
        sconf.source.repoUrl = si.source.repo_url

        engine = SyncEngine(bconf, sconf, incoming_suite)

        blacklist_pkgnames = get_package_blacklist()
        engine.setSourceSuite(si.source.suite_name)
        engine.setBlacklist(blacklist_pkgnames)

        ret = engine.syncPackages(options.component, options.packages, options.force)
        publish_synced_spkg_events(engine,
                                   si.source.os_name,
                                   si.source.suite_name,
                                   si.destination_suite.name,
                                   options.force)
        if not ret:
            sys.exit(2)


def command_autosync(options):
    ''' Automatically synchronize packages '''

    with session_scope() as session:
        autosyncs = session.query(SynchrotronConfig).filter(SynchrotronConfig.sync_enabled == True) \
            .filter(SynchrotronConfig.sync_auto_enabled == True).all()  # noqa: E712

        bconf, sconf = get_sync_config()
        blacklist_pkgnames = get_package_blacklist()  # the blacklist is global for now

        for autosync in autosyncs:
            incoming_suite = get_suiteinfo_for_suite(autosync.destination_suite)
            sconf.syncBinaries = autosync.sync_binaries
            sconf.source.defaultSuite = autosync.source.suite_name
            sconf.source.repoUrl = autosync.source.repo_url

            log.info('Synchronizing packages from {}/{} with {}'.format(autosync.source.os_name, autosync.source.suite_name,
                                                                        autosync.destination_suite.name))

            emitter = EventEmitter(LkModule.SYNCHROTRON)

            engine = SyncEngine(bconf, sconf, incoming_suite)
            engine.setBlacklist(blacklist_pkgnames)

            ret, issue_data = engine.autosync()
            publish_synced_spkg_events(engine,
                                       autosync.source.os_name,
                                       autosync.source.suite_name,
                                       autosync.destination_suite.name,
                                       emitter=emitter)
            if not ret:
                sys.exit(2)
                return

            for ssuite in sconf.source.suites:
                session.query(SynchrotronIssue) \
                    .filter(SynchrotronIssue.source_suite == ssuite.name,
                            SynchrotronIssue.target_suite == incoming_suite.name,
                            SynchrotronIssue.config_id == autosync.id) \
                    .delete()

            for info in issue_data:
                issue = SynchrotronIssue()
                issue.config = autosync
                issue.kind = SynchrotronIssueKind(info.kind)
                issue.package_name = info.packageName
                issue.source_suite = info.sourceSuite
                issue.target_suite = info.targetSuite
                issue.source_version = info.sourceVersion
                issue.target_version = info.targetVersion
                issue.details = info.details
                session.add(issue)

                data = {'name': issue.package_name,
                        'src_os': autosync.source.os_name,
                        'src_suite': issue.source_suite,
                        'dest_suite': issue.target_suite,
                        'src_version': issue.source_version,
                        'dest_version': issue.target_version,
                        'kind': str(issue.kind)}

                emitter.submit_event('autosync-issue', data)


def create_parser(formatter_class=None):
    ''' Create synchrotron CLI argument parser '''

    parser = ArgumentParser(description='Synchronize packages with another distribution')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('sync', help='Synchronize a package or set of packages')
    sp.add_argument('--force', action='store_true', dest='force', help='Force package import and ignore version conflicts.')
    sp.add_argument('src_suite', type=str, help='The suite to synchronize from')
    sp.add_argument('dest_suite', type=str, help='The suite to synchronize to')
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
