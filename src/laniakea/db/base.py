# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import Any
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

from ..utils import cd
from ..logging import log
from ..localconfig import LocalConfig

__all__ = ['Base', 'DebVersion', 'Database', 'UUID', 'session_scope', 'create_tsvector', 'print_query']


Base: Any = declarative_base()


# Patch in support for the debversion field type so that it works during
# reflection
# pylint: disable=abstract-method,no-init
class DebVersion(UserDefinedType):
    def get_col_spec(self):
        return 'DEBVERSION'

    def bind_processor(self, dialect):
        return None

    def result_processor(self, dialect, coltype):
        return None


from sqlalchemy.databases import postgres

postgres.ischema_names['debversion'] = DebVersion


class Database:
    instance = None

    class __Database:
        def __init__(self, lconf=None):
            if not lconf:
                lconf = LocalConfig()
            self._lconf = lconf

            self._engine = create_engine(self._lconf.database_url, client_encoding='utf8')
            self._SessionFactory = sessionmaker(bind=self._engine)

        def create_tables(self):
            '''Initialize the database and create all tables'''
            from alembic import command
            from alembic.config import Config

            from .. import lk_py_directory

            with cd(lk_py_directory):
                Base.metadata.create_all(self._engine)
                alembic_cfg = Config(os.path.join(lk_py_directory, 'alembic.ini'))
                command.stamp(alembic_cfg, "head")
            self.upgrade()

        def upgrade(self):
            '''Upgrade database schema to the newest revision'''
            import alembic.config

            from .. import lk_py_directory

            with cd(lk_py_directory):
                alembicArgs = [
                    '--raiseerr',
                    'upgrade',
                    'head',
                ]
                alembic.config.main(argv=alembicArgs)
            self._update_static_data()
            log.info('Database upgrade done.')

        def _update_static_data(self):
            import json

            from .archive import (
                ArchiveConfig,
                ArchiveSection,
                ArchiveRepository,
                ArchiveArchitecture,
            )
            from ..localconfig import get_data_file

            log.info('Updating static database data.')
            with open(get_data_file('archive-sections.json'), 'r') as f:
                sections_seed = json.load(f)

            # update data
            with session_scope() as session:
                for jsec in sections_seed:
                    if 'name' not in jsec:
                        raise Exception('Invalid section contained in archive sections file (name missing).')
                    if 'summary' not in jsec:
                        jsec['summary'] = 'The {} section'.format(jsec['name'])

                    section = session.query(ArchiveSection).filter(ArchiveSection.name == jsec['name']).one_or_none()
                    if section:
                        section.summary = jsec['summary']
                    else:
                        section = ArchiveSection(jsec['name'], jsec['summary'])
                        session.add(section)

                master_repo_name = self._lconf.master_repo_name
                if not master_repo_name:
                    raise ValueError('No name set for the master repository of this distribution!')
                master_debug_repo_name = '{}-debug'.format(master_repo_name)

                aconfig = session.query(ArchiveConfig).first()
                if not aconfig:
                    master_repo = (
                        session.query(ArchiveRepository)
                        .filter(ArchiveRepository.name == master_repo_name)
                        .one_or_none()
                    )
                    master_debug_repo = (
                        session.query(ArchiveRepository)
                        .filter(ArchiveRepository.name == master_debug_repo_name)
                        .one_or_none()
                    )
                    if not master_repo:
                        master_repo = ArchiveRepository(master_repo_name)
                        session.add(master_repo)
                    if not master_debug_repo:
                        master_debug_repo = ArchiveRepository(master_debug_repo_name)
                        session.add(master_debug_repo)

                    # set up repo<->debug-repo relation
                    master_debug_repo.is_debug = True
                    master_repo.debug_repo = master_debug_repo
                    master_repo.is_debug = False

                    # set primary repository
                    aconfig = ArchiveConfig()
                    aconfig.primary_repo = master_repo
                    aconfig.archive_url = self._lconf.archive_url
                    session.add(aconfig)

                # arch:all architecture
                arch_all = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == 'all').one_or_none()
                if not arch_all:
                    arch_all = ArchiveArchitecture('all')
                    arch_all.summary = 'Architecture independent binaries'
                    session.add(arch_all)

        def downgrade(self, revision):
            '''Upgrade database schema to the newest revision'''
            import alembic.config

            from .. import lk_py_directory

            with cd(lk_py_directory):
                alembicArgs = [
                    '--raiseerr',
                    'downgrade',
                    revision,
                ]
                alembic.config.main(argv=alembicArgs)

    def __init__(self, lconf=None):
        if not Database.instance:
            Database.instance = Database.__Database(lconf)

    def __getattr__(self, name):
        return getattr(self.instance, name)


def session_factory():
    db = Database()
    return db._SessionFactory()


@contextmanager
def session_scope():
    '''
    Provide a transactional scope around a series of operations.
    '''
    session = session_factory()
    try:
        yield session
        session.commit()
    except:  # noqa: E722
        session.rollback()
        raise
    finally:
        session.close()


def create_tsvector(*args):
    exp = args[0]
    for e in args[1:]:
        exp += ' ' + e
    return func.to_tsvector('english', exp)


def print_query(query, literals=True):
    '''
    Print a SQLAlchemy query with literals inserted and
    adjusted for the PostgreSQL dialect.
    '''
    from sqlalchemy.dialects import postgresql

    sql = query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': literals})
    print('---- SQL ({} literals) ----'.format('with' if literals else 'without'))
    print(str(sql))
