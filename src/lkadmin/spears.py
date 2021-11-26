# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click

from laniakea.db import session_factory

from .utils import input_int, input_str, input_bool, input_list, print_header


@click.group()
def spears():
    '''Configure automatic package migration.'''


@spears.command()
def configure_all():
    '''Configure this module.'''

    from laniakea.db import VersionPriority, SpearsMigrationEntry

    print_header('Configuring settings for Spears (migrations)')

    session = session_factory()

    add_migration = True
    while add_migration:
        entry = SpearsMigrationEntry()

        entry.source_suites = input_list('Migrate from suites (source names)')
        entry.target_suite = input_str('Migrate to suite (target name)')

        entry.delays = {}
        for prio in VersionPriority:
            entry.delays[int(prio)] = input_int('Delay for packages of priority "{}" in days'.format(repr(prio)))

        # FIXME: We need to check for uniqueness of the migration task!
        entry.idname = entry.make_migration_id()
        session.add(entry)
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
