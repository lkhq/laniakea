# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click

from laniakea.db import session_factory

from .utils import input_str, print_header


@click.group()
def core():
    '''Elemental functions affecting all of Laniakea.'''


@core.command()
def db_init():
    '''Initialize database schemas on an empty database.'''
    from laniakea.db import Database

    db = Database()
    db.create_tables()

    print('Database tables created.')


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

    db_init()
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
