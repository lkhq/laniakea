# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click
from rich.prompt import Prompt

from laniakea import LocalConfig
from laniakea.db import ArchiveSuite, ArchiveRepository, session_factory

from .utils import input_int, input_str, input_bool, input_list, print_header


@click.group()
def spears():
    '''Configure automatic package migration.'''


@spears.command()
def configure_all():
    '''Configure this module.'''

    from laniakea.db import ChangesUrgency, SpearsMigrationTask

    print_header('Configuring settings for Spears (migrations)')

    session = session_factory()

    add_migration = True
    while add_migration:
        stask = SpearsMigrationTask()

        repo_name = Prompt.ask('Repository name to add migration task for', default=LocalConfig().master_repo_name)
        stask.repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()

        for suite_name in input_list('Migrate from suites (source names)'):
            stask.source_suites.append(session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one())

        target_suite_name = input_str('Migrate to suite (target name)')
        stask.target_suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == target_suite_name).one()

        stask.delays = {}
        for prio in ChangesUrgency:
            stask.delays[prio.to_string()] = input_int(
                'Delay for packages of priority "{}" in days'.format(prio.to_string())
            )

        # FIXME: We need to check for uniqueness of the migration task!
        session.add(stask)
        session.commit()

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

    session = session_factory()

    migration_id = '{}-to-{}'.format(source_suite, target_suite)

    # remove a preexisting hint
    session.query(SpearsHint).filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == hint).delete()

    h = SpearsHint()
    h.migration_id = migration_id
    h.hint = hint
    h.reason = reason

    session.add(h)
    session.commit()


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

    session = session_factory()

    migration_id = '{}-to-{}'.format(source_suite, target_suite)
    session.query(SpearsHint).filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == hint).delete()
