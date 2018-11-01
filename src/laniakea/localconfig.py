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

import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class LocalConfig:
    '''
    Local, machine-specific configuration for a Laniakea module.
    '''

    instance = None

    class __LocalConfig:

        def __init__(self, fname=None):
            if not fname:
                fname = '/etc/laniakea/base-config.json'

            jdata = {}
            if os.path.isfile(fname):
                with open(fname) as json_file:
                    jdata = json.load(json_file)

            self._project_name = jdata.get('ProjectName', '')


            jdb = jdata.get('Database', {})
            databaseHost = jdb.get('host', 'localhost')
            databasePort = int(jdb.get('port', 5432))
            databaseName = jdb.get('db', 'laniakea')
            databaseUser = jdb.get('user', 'laniakea-user')
            databasePassword = jdb.get('password', '')

            self._database_url = 'postgresql://{user}:{password}@{host}:{port}/{dbname}'.format(user=databaseUser,
                                                                                                password=databasePassword,
                                                                                                host=databaseHost,
                                                                                                port=databasePort,
                                                                                                dbname=databaseName)


        @property
        def project_name(self) -> str:
            return self._project_name

        @property
        def database_url(self) -> str:
            return self._database_url

        @property
        def session_factory(self):
            return self._session_factory


    def __init__(self, fname=None):
        if not LocalConfig.instance:
            LocalConfig.instance = LocalConfig.__LocalConfig(fname)

    def __getattr__(self, name):
        return getattr(self.instance, name)
