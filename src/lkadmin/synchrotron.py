# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click
from rich.prompt import Prompt

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    ArchiveRepository,
    SynchrotronConfig,
    SynchrotronSource,
    SyncBlacklistEntry,
    session_scope,
)

from .utils import input_str, input_bool, input_list, print_note, print_error_exit


@click.group()
def synchrotron():
    '''Adjust package synchronization settings.'''


@synchrotron.command()
def add_source():
    """Add a source repository."""

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
            sync_source.architectures = input_list(
                'List of architectures for suite \'{}\''.format(sync_source.suite_name)
            )

            session.add(sync_source)
            add_suite = input_bool('Add another suite?')


@synchrotron.command()
def update_task():
    """Add or update a synchronization task."""

    add_sync_tasks = True
    while add_sync_tasks:
        with session_scope() as session:
            repo_name = Prompt.ask('Repository name to add sync task for', default=LocalConfig().master_repo_name)
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()

            sync_source = None
            while not sync_source:
                src_os = input_str('Source OS name')
                src_suite = input_str('Source suite name')
                sync_source = (
                    session.query(SynchrotronSource)
                    .filter(SynchrotronSource.os_name == src_os, SynchrotronSource.suite_name == src_suite)
                    .one_or_none()
                )
                if not sync_source:
                    print_note('Could not find sync source with suite name "{}/{}"'.format(src_os, src_suite))

            dest_suite = None
            while not dest_suite:
                dest_suite_name = input_str('Destination suite name')
                dest_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == dest_suite_name).one_or_none()
                if not dest_suite:
                    print_note('Could not find suite with name "{}"'.format(dest_suite_name))

            autosync = (
                session.query(SynchrotronConfig)
                .filter(
                    SynchrotronConfig.repo_id == repo.id,
                    SynchrotronConfig.source_id == sync_source.id,
                    SynchrotronConfig.destination_suite_id == dest_suite.id,
                )
                .one_or_none()
            )
            if autosync:
                print('Found existing sync configuration, updating it in the next steps.')
            else:
                autosync = SynchrotronConfig()
                autosync.repo = repo
                autosync.source = sync_source
                autosync.destination_suite = dest_suite
                session.add(autosync)

            autosync.sync_auto_enabled = input_bool('Enable automatic synchronization?')
            autosync.sync_enabled = input_bool('Enable synchronization?')
            autosync.sync_binaries = input_bool('Synchronize binary packages?')

            add_sync_tasks = input_bool('Add another sync task?')


def _get_sync_conf(session, src_os_name, src_suite_name, repo_name, dest_suite_name) -> T.Optional[SynchrotronConfig]:
    sync_source = (
        session.query(SynchrotronSource)
        .filter(SynchrotronSource.os_name == src_os_name, SynchrotronSource.suite_name == src_suite_name)
        .one_or_none()
    )
    if not sync_source:
        print_note('Could not find sync source with suite name "{}/{}"'.format(src_os_name, src_suite_name))
        return None

    dest_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == dest_suite_name).one_or_none()
    if not dest_suite:
        print_note('Could not find suite with name "{}"'.format(dest_suite_name))
        return None

    return (
        session.query(SynchrotronConfig)
        .filter(
            SynchrotronConfig.repo.has(name=repo_name),
            SynchrotronConfig.source_id == sync_source.id,
            SynchrotronConfig.destination_suite_id == dest_suite.id,
        )
        .one_or_none()
    )


@synchrotron.command()
@click.option('--repo', 'repo_name', prompt=True, type=str, help='Name of the repository.')
@click.option('--src-os', 'src_os_name', prompt=True, type=str, help='Name of the source OS.')
@click.option('--src-suite', 'src_suite_name', prompt=True, type=str, help='Name of the source suite.')
@click.option('--dest-suite', 'dest_suite_name', prompt=True, type=str, help='Name of the destination suite.')
@click.argument('pkgname', nargs=1)
@click.argument('reason', nargs=1)
def blacklist_add(src_os_name, src_suite_name, repo_name, dest_suite_name, pkgname, reason):
    """Blacklist a package from automatic sync."""

    with session_scope() as session:
        sync_conf = _get_sync_conf(session, src_os_name, src_suite_name, repo_name, dest_suite_name)
        if not sync_conf:
            print_error_exit('No sync configuration was found with the given setting.')

        # delete existing entry in case it exists
        entry = (
            session.query(SyncBlacklistEntry)
            .filter(SyncBlacklistEntry.config_id == sync_conf.id, SyncBlacklistEntry.pkgname == pkgname)
            .one_or_none()
        )
        if entry:
            print_note('Updating existing entry for this package.')
        else:
            entry = SyncBlacklistEntry()
            entry.config = sync_conf
            session.add(entry)
        entry.pkgname = pkgname
        entry.reason = reason


@synchrotron.command()
@click.option('--repo', 'repo_name', prompt=True, type=str, help='Name of the repository.')
@click.option('--src-os', 'src_os_name', prompt=True, type=str, help='Name of the source OS.')
@click.option('--src-suite', 'src_suite_name', prompt=True, type=str, help='Name of the source suite.')
@click.option('--dest-suite', 'dest_suite_name', prompt=True, type=str, help='Name of the destination suite.')
@click.argument('pkgname', nargs=1)
def blacklist_remove(src_os_name, src_suite_name, repo_name, dest_suite_name, pkgname):
    """Remove a package from the sync blacklist."""

    with session_scope() as session:
        sync_conf = _get_sync_conf(session, src_os_name, src_suite_name, repo_name, dest_suite_name)
        if not sync_conf:
            print_error_exit('No sync configuration was found with the given setting.')

        # delete existing entry in case it exists
        entry = (
            session.query(SyncBlacklistEntry)
            .filter(SyncBlacklistEntry.config_id == sync_conf.id, SyncBlacklistEntry.pkgname == pkgname)
            .one_or_none()
        )
        if entry:
            session.delete(entry)
        else:
            print_note('The selected package was not blacklisted. Nothing was removed.')
