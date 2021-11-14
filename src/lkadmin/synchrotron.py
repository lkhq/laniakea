# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import click
from .utils import print_header, print_section, print_note, input_str, input_bool, input_list
from laniakea.db import session_scope, SynchrotronSource, SynchrotronConfig, SyncBlacklistEntry, \
    ArchiveSuite


@click.group()
def synchrotron():
    ''' Adjust package synchronization settings. '''
    pass


@synchrotron.command()
def configure_all():
    ''' Configure this module. '''

    print_header('Configuring base settings for Synchrotron')
    print_section('Add synchronization sources')

    source_distro_name = input_str('Name of the source distribution')
    source_repo_url = input_str('Source repository URL')

    add_suite = input_bool('Add a new source suite?')
    while add_suite:
        with session_scope() as session:
            sync_source = SynchrotronSource()

            sync_source.os_name = source_distro_name
            sync_source.repo_url = source_repo_url
            sync_source.suite_name = input_str('Adding a new source suite. Please set a name')

            sync_source.components = input_list('List of components for suite \'{}\''.format(sync_source.suite_name))
            sync_source.architectures = input_list('List of architectures for suite \'{}\''.format(sync_source.suite_name))

            session.add(sync_source)
            add_suite = input_bool('Add another suite?')

    print_section('Add sync tasks')
    add_sync_tasks = True
    while add_sync_tasks:
        with session_scope() as session:
            autosync = SynchrotronConfig()
            sync_source = None
            while not sync_source:
                src_suite = input_str('Source suite name')
                sync_source = session.query(SynchrotronSource).filter(SynchrotronSource.suite_name == src_suite).one_or_none()
                if not sync_source:
                    print_note('Could not find sync source with suite name "{}"'.format(src_suite))
            autosync.source = sync_source

            dest_suite = None
            while not dest_suite:
                dest_suite_name = input_str('Destination suite name')
                dest_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == dest_suite_name).one_or_none()
                if not dest_suite:
                    print_note('Could not find suite with name "{}"'.format(dest_suite_name))
            autosync.destination_suite = dest_suite

            autosync.sync_auto_enabled = input_bool('Enable automatic synchronization?')
            autosync.sync_enabled = input_bool('Enable synchronization?')
            autosync.sync_binaries = input_bool('Synchronize binary packages?')

            session.add(autosync)
            add_sync_tasks = input_bool('Add another sync task?')


@synchrotron.command()
@click.argument('pkgname', nargs=1)
@click.argument('reason', nargs=1)
def blacklist_add(pkgname, reason):
    ''' Blacklist a package from automatic sync.
    Takes package name as first, and reason as second parameter.'''

    with session_scope() as session:
        # delete existing entry in case it exists
        entry = session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.pkgname == pkgname).one_or_none()
        if entry:
            print_note('Updating existing entry for this package.')
        else:
            entry = SyncBlacklistEntry()
            session.add(entry)
        entry.pkgname = pkgname
        entry.reason = reason


@synchrotron.command()
@click.argument('pkgname', nargs=1)
def blacklist_remove(pkgname):
    ''' Remove a package from the sync blacklist. '''

    with session_scope() as session:
        # delete existing entry in case it exists
        entry = session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.pkgname == pkgname).one_or_none()
        if entry:
            session.delete(entry)
        else:
            print_note('The selected package was not in blacklist. Nothing was removed.')
