# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import click
from laniakea.db import session_factory, session_scope
from .utils import print_header, print_note, input_str, input_bool, input_list


@click.group()
def core():
    ''' Elemental functions affecting all of Laniakea. '''
    pass


@core.command()
def db_init():
    ''' Initialize database schemas on an empty database. '''
    from laniakea.db import Database
    db = Database()
    db.create_tables()

    print('Database tables created.')


@core.command()
def db_upgrade():
    ''' Upgrade database schemas to latest version. '''
    from laniakea.db import Database
    db = Database()
    db.upgrade()

    print('Database upgraded.')


def _add_new_suite(session):
    '''
    Interactively register a new suite.
    '''
    from laniakea.db import ArchiveRepository, ArchiveSuite, ArchiveComponent, ArchiveArchitecture

    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name == 'master').one()

    suite_name = input_str('Adding a new suite. Please set a name')

    suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.name == suite_name).one_or_none()
    if suite:
        print_note('Removing existing suite with the same name ("{}")'.format(suite_name))
        session.delete(suite)
        session.commit()

    suite = ArchiveSuite(suite_name)
    suite.repos = [repo]

    component_names = input_list('List of components for suite "{}"'.format(suite.name))
    add_main_dep = 'main' in component_names
    if add_main_dep:
        component_names.remove('main')
        component_names.insert(0, 'main')

    suite.components = []
    main_component = None
    for cname in component_names:
        component = session.query(ArchiveComponent) \
            .filter(ArchiveComponent.name == cname).one_or_none()
        if not component:
            component = ArchiveComponent(cname)
            if add_main_dep and main_component and cname != 'main':
                component.parent_component = main_component
            session.add(component)
        if cname == 'main':
            main_component = component
        suite.components.append(component)

    arch_names = input_list('List of architectures for suite "{}"'.format(suite.name))
    # every suite has the "all" architecture, so add it straight away
    if 'all' not in arch_names:
        arch_names.insert(0, 'all')

    suite.architectures = []
    for aname in arch_names:
        arch = session.query(ArchiveArchitecture) \
            .filter(ArchiveArchitecture.name == aname).one_or_none()
        if not arch:
            arch = ArchiveArchitecture(aname)
            session.add(arch)
        suite.architectures.append(arch)

    parent_suite = None
    while not parent_suite:
        parent_suite_name = input_str('Set a name of the suite this suite is an overlay to. Leave empty for primary suite. (The overlay suite must have been added first!)',
                                      allow_empty=True)
        if not parent_suite_name:
            break

        parent_suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == parent_suite_name).one_or_none()
        if not parent_suite:
            print_note('Parent suite "{}" was not found.'.format(parent_suite_name))
        suite.parent = parent_suite

    session.add(suite)
    session.commit()


@core.command()
def configure_all():
    ''' Configure all basic settings in one go. '''
    from laniakea.db.core import config_set_project_name, config_set_distro_tag
    from laniakea.db import ArchiveRepository, ArchiveSuite

    db_init()
    print_header('Configuring base settings for Laniakea')
    session = session_factory()

    config_set_project_name(input_str('Name of this project'))

    # we only support one repository at time, so add the default
    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name == 'master').one_or_none()
    if not repo:
        repo = ArchiveRepository('master')
        session.add(repo)
        session.commit()

    add_suite = True
    while add_suite:
        _add_new_suite(session)
        add_suite = input_bool('Add another suite?')

    incoming_suite = None
    while not incoming_suite:
        incoming_suite_name = input_str('Name of the \'incoming\' suite which new packages are usually uploaded to')
        incoming_suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == incoming_suite_name).one_or_none()
        if not incoming_suite:
            print_note('Suite with the name "{}" was not found.'.format(incoming_suite_name))
        incoming_suite.accept_uploads = True

    devel_suite = None
    while not devel_suite:
        devel_suite_name = input_str('Name of the "development" suite which is rolling or will become a final release')
        devel_suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == devel_suite_name).one_or_none()
        if not devel_suite:
            print_note('Suite with the name "{}" was not found.'.format(devel_suite_name))
        devel_suite.devel_target = True

    config_set_distro_tag(input_str('Distribution version tag (commonly found in package versions, e.g. \'tanglu\' for OS \'Tanglu\' with versions like \'1.0-0tanglu1\''))
    session.commit()


@core.command()
def add_suite():
    ''' Add a new archive suite. '''
    with session_scope() as session:
        _add_new_suite(session)


@core.command()
def delete_suite(options):
    ''' Delete an archive suite. '''
    from laniakea.db import ArchiveSuite

    suite_name = options.delete_suite
    if not suite_name:
        print('No suite name was given!')
        sys.exit(1)

    if not input_bool('Do you really want to remove suite "{}" and all its associcated data?'.format(suite_name)):
        sys.exit(3)

    with session_scope() as session:
        suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == suite_name).one_or_none()
        if not suite:
            print('A suite with name "{}" was not found!'.format(suite_name))
            sys.exit(4)
        session.delete(suite)
