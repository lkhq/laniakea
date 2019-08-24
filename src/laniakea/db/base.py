# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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


from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from contextlib import contextmanager
from ..localconfig import LocalConfig
from ..utils import cd


__all__ = ['Base',
           'DebVersion',
           'Database',
           'UUID',
           'session_scope',
           'create_tsvector',
           'print_query']


Base = declarative_base()


# Patch in support for the debversion field type so that it works during
# reflection
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
            ''' Initialize the database and create all tables '''
            self.upgrade()
            Base.metadata.create_all(self._engine)

        def upgrade(self):
            ''' Upgrade database schema to the newest revision '''
            import alembic.config
            from .. import lk_py_directory

            with cd(lk_py_directory):
                alembicArgs = [
                    '--raiseerr',
                    'upgrade', 'head',
                ]
                alembic.config.main(argv=alembicArgs)

        def downgrade(self, revision):
            ''' Upgrade database schema to the newest revision '''
            import alembic.config
            from .. import lk_py_directory

            with cd(lk_py_directory):
                alembicArgs = [
                    '--raiseerr',
                    'downgrade', revision,
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
