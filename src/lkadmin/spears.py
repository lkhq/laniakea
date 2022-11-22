# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click
import tomlkit
from rich.prompt import Prompt

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import ArchiveSuite, ArchiveRepository, session_scope

from .utils import (
    input_int,
    input_str,
    input_bool,
    input_list,
    print_header,
    print_error_exit,
)


@click.group()
def spears():
    '''Configure automatic package migration.'''


def _add_migration_task(repo_name: str, source_suites: T.List[str], target_suite: str, delays: dict[str, int]):
    """Add or update a migration task."""

    from laniakea.db import ChangesUrgency, SpearsMigrationTask

    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()
        target_suite_e = session.query(ArchiveSuite).filter(ArchiveSuite.name == target_suite).one()

        stask = (
            session.query(SpearsMigrationTask)
            .filter(SpearsMigrationTask.repo_id == repo.id)
            .filter(SpearsMigrationTask.target_suite_id == target_suite_e.id)
            .one_or_none()
        )
        if not stask:
            stask = SpearsMigrationTask()
            session.add(stask)

        stask.repo = repo
        stask.target_suite = target_suite_e

        for suite_name in source_suites:
            stask.source_suites.append(session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one())

        stask.delays = {}
        for prio_name, days in delays.items():
            if ChangesUrgency.from_string(prio_name) == ChangesUrgency.UNKNOWN:
                raise ValueError('The priority value "{}" is unknown!'.format(prio_name))
            stask.delays[prio_name] = days


@spears.command()
def configure_all():
    '''Configure this module.'''

    from laniakea.db import ChangesUrgency

    print_header('Configuring settings for Spears (migrations)')

    add_migration = True
    while add_migration:
        repo_name = Prompt.ask('Repository name to add migration task for', default=LocalConfig().master_repo_name)

        to_suite = input_str('Migrate to suite (target name)')
        from_suites = input_list('Migrate from suites (source names)')

        delays = {}
        for prio in ChangesUrgency:
            delays[prio.to_string()] = input_int('Delay for packages of priority "{}" in days'.format(prio.to_string()))

        _add_migration_task(repo_name, from_suites, to_suite, delays)

        add_migration = input_bool('Add another migration task?')


@spears.command()
@click.argument('source_suite', nargs=1)
@click.argument('target_suite', nargs=1)
@click.argument('hint', nargs=1)
@click.argument('reason', nargs=1)
def add_hint(source_suite, target_suite, hint, reason):
    '''Add a migration hint.
    SOURCE_SUITE: Source suite of the package.
    TARGET_SUITE: Target suite of the package.
    HINT: Britney hint string.
    REASON: Reason for adding this hint.
    '''

    from laniakea.db import SpearsHint

    with session_scope() as session:
        migration_id = '{}-to-{}'.format(source_suite, target_suite)

        # remove a preexisting hint
        session.query(SpearsHint).filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == hint).delete()

        h = SpearsHint()
        h.migration_id = migration_id
        h.hint = hint
        h.reason = reason

        session.add(h)


@spears.command()
@click.argument('source_suite', nargs=1)
@click.argument('target_suite', nargs=1)
@click.argument('hint', nargs=1)
def remove_hint(source_suite, target_suite, hint):
    '''Remove a migration hint.
    SOURCE_SUITE: Source suite of the package.
    TARGET_SUITE: Target suite of the package.
    HINT: Britney hint string.
    REASON: Reason for adding this hint.
    '''

    from laniakea.db import SpearsHint

    with session_scope() as session:
        migration_id = '{}-to-{}'.format(source_suite, target_suite)
        session.query(SpearsHint).filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == hint).delete()


@spears.command()
@click.argument('config_fname', nargs=1)
def add_from_config(config_fname):
    """Add/update migration tasks from a TOML config file."""
    try:
        with open(config_fname, 'r', encoding='utf-8') as f:
            conf = tomlkit.load(f)
    except Exception as e:
        print_error_exit('Unable to load data from configuration file: {}'.format(str(e)))

    for task_d in conf.get('MigrationTasks', []):
        _add_migration_task(**task_d)
