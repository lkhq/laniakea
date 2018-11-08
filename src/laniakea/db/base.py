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
from sqlalchemy.dialects.postgresql import UUID
from ..localconfig import LocalConfig


Base = declarative_base()

class Database:
    instance = None

    class __Database:
        def __init__(self, lconf=None):
            if not lconf:
                lconf = LocalConfig()
            self._lconf = lconf

            self._engine = create_engine(self._lconf.database_url)
            self._SessionFactory = sessionmaker(bind=self._engine)

        def create_tables(self):
            Base.metadata.create_all(self._engine)

    def __init__(self, lconf=None):
        if not Database.instance:
            Database.instance = Database.__Database(lconf)

    def __getattr__(self, name):
        return getattr(self.instance, name)


def session_factory():
    db = Database()
    return db._SessionFactory()
