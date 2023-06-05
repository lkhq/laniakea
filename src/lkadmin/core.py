# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import platform
from datetime import datetime

import click

from laniakea import LkModule
from laniakea.db import session_scope, session_factory

from .utils import input_str, print_header, print_error_exit


@click.group()
def core():
    '''Elemental functions affecting all of Laniakea.'''


def _db_init():
    '''Helper to initialize database schemas on an empty database.'''
    from laniakea.db import Database

    db = Database()
    db.create_tables()

    print('Database tables created.')


@core.command()
def db_init():
    '''Initialize database schemas on an empty database.'''
    _db_init()


@core.command()
def db_upgrade():
    '''Upgrade database schemas to latest version.'''
    from laniakea.db import Database

    db = Database()
    db.upgrade()

    print('Database upgraded.')


@core.command()
def configure_all():
    '''Configure all basic settings in one go.'''
    from laniakea.db.core import config_set_distro_tag, config_set_project_name

    _db_init()
    print_header('Configuring base settings for Laniakea')
    session = session_factory()

    config_set_project_name(input_str('Name of this project'))

    config_set_distro_tag(
        input_str(
            'Distribution version tag (commonly found in package versions, '
            'e.g. \'tanglu\' for OS \'Tanglu\' with versions like \'1.0-0tanglu1\''
        )
    )
    session.commit()


@core.command()
def send_ping():
    """Emit ping event over the ZeroMQ publication channels."""
    from laniakea.msgstream import EventEmitter

    emitter = EventEmitter(LkModule.BASE)
    emitter.submit_event(
        'ping', {'node': platform.node(), 'message': 'Hello World!', 'time_sent': str(datetime.now().isoformat())}
    )


@core.command()
def shell():
    """Launch interactive bpython shell."""

    try:
        import bpython
    except ImportError:
        print_error_exit('Could not find `bpython`! Please install bpython to use this command.')

    # flake8: noqa
    # pylint: disable=possibly-unused-variable
    import laniakea.db as db

    # pylint: disable=possibly-unused-variable
    with session_scope() as session:
        bpython.embed(locals_=locals())
