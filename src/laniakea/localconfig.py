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
import platform
from glob import glob
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_config_file(fname):
    '''
    Determine the path of a local Laniakea configuration file.
    '''

    path = os.path.join('/etc/laniakea/', fname)
    if os.path.isfile(path):
        return path
    path = os.path.join('config', fname)
    if os.path.isfile(path):
        return path
    return None


class LocalConfig:
    '''
    Local, machine-specific configuration for a Laniakea module.
    '''

    instance = None

    class __LocalConfig:

        def __init__(self, fname=None):
            if not fname:
                fname = get_config_file('base-config.json')

            jdata = {}
            if os.path.isfile(fname):
                with open(fname) as json_file:
                    jdata = json.load(json_file)

            self._project_name = jdata.get('ProjectName', '')

            jarchive = jdata.get('Archive')
            if not jarchive:
                raise Exception('No "Archive" configuration found in local config file. Please specify archive details!')

            self._workspace = jdata.get('Workspace')
            if not self._workspace:
                raise Exception('No "Workspace" directory set in local config file. Please specify a persistent workspace location!')

            self._cache_dir = jdata.get('CacheLocation', '/var/tmp/laniakea')

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

            self._archive_root_dir = jarchive['path']
            self._archive_url = jarchive.get('url', '#')

            self._lighthouse_endpoint = jdata.get('LighthouseEndpoint')


            # Synchrotron-specific configuration
            self._synchrotron_sourcekeyrings = []
            if 'Synchrotron' in jdata:
                from glob import glob
                syncconf = jdata.get('Synchrotron')
                if 'SourceKeyringDir' in syncconf:
                    self._synchrotron_sourcekeyrings = glob(os.path.join(syncconf['SourceKeyringDir'], '*.gpg'))

            # ZCurve
            self._zcurve_keys_basedir = '/etc/laniakea/keys/curve/'

            # Trusted GPG keyrings
            self._trusted_gpg_keyrings = []
            self._trusted_gpg_keyring_dir = jdata.get('TrustedGpgKeyringDir')
            if self._trusted_gpg_keyring_dir:
                self._trusted_gpg_keyrings = [glob(os.path.join(self._trusted_gpg_keyring_dir, '*.gpg'))]

        @property
        def project_name(self) -> str:
            return self._project_name

        @property
        def workspace(self) -> str:
            return self._workspace

        @property
        def cache_dir(self) -> str:
            return self._cache_dir

        @property
        def database_url(self) -> str:
            return self._database_url

        @property
        def archive_root_dir(self) -> str:
            return self._archive_root_dir

        @property
        def archive_url(self) -> str:
            return self._archive_url

        @property
        def lighthouse_endpoint(self) -> str:
            return self._lighthouse_endpoint

        @property
        def synchrotron_sourcekeyrings(self) -> str:
            return self._synchrotron_sourcekeyrings


        def zcurve_secret_keyfile_for_module(self, module) -> str:
            ''' Retrieve the secret ZCurve key filename for a given module name. '''

            secrets_dir = os.path.join(self._zcurve_keys_basedir, 'secret')
            try:
                os.makedirs(secrets_dir, exist_ok=True)
            except:
                pass

            return os.path.join(secrets_dir, '{}-{}_private.sec'.format(platform.node(), module))

        @property
        def zcurve_trusted_certs_dir(self) -> str:
            ''' Retrieve the directory for trusted ZCurve public keys '''

            trusted_dir = os.path.join(self._zcurve_keys_basedir, 'trusted')
            try:
                os.makedirs(trusted_dir, exist_ok=True)
            except:
                pass

            return trusted_dir

        @property
        def trusted_gpg_keyring_dir(self) -> str:
            return self._trusted_gpg_keyring_dir

        @property
        def trusted_gpg_keyrings(self) -> list:
            return self._trusted_gpg_keyrings


    def __init__(self, fname=None):
        if not LocalConfig.instance:
            LocalConfig.instance = LocalConfig.__LocalConfig(fname)

    def __getattr__(self, name):
        return getattr(self.instance, name)


class ExternalToolsUrls:
    '''
    Fetch URLs for external tools.
    '''

    def __init__(self, fname=None):
        if not fname:
            fname = '/usr/share/laniakea/3rd-party.json'

        jdata = {}
        if os.path.isfile(fname):
            with open(fname) as json_file:
                jdata = json.load(json_file)

        jspears = jdata.get('Spears', {})
        self.britney_git_repository = jspears.get('britneyGitRepository', 'https://salsa.debian.org/release-team/britney2.git')
