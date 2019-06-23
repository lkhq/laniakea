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


def get_data_file(fname):
    '''
    Determine the path of a local Laniakea data file.
    '''
    thisfile = __file__
    if not os.path.isabs(thisfile):
        thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
    if thisfile.startswith('/usr'):
        if thisfile.startswith('/usr/local'):
            path = os.path.join('/usr/local/share/laniakea/', fname)
        else:
            path = os.path.join('/usr/share/laniakea/', fname)
    else:
        # we run from a non-installed (development?) directory
        path = os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', '..', 'data', fname))

    return path


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

            jarchive = jdata.get('Archive')
            if not jarchive:
                raise Exception('No "Archive" configuration found in local config file. Please specify archive details!')

            self._workspace = jdata.get('Workspace')
            if not self._workspace:
                raise Exception('No "Workspace" directory set in local config file. Please specify a persistent workspace location!')

            self._cache_dir = jdata.get('CacheLocation', '/var/tmp/laniakea')

            jdb = jdata.get('Database', {})
            db_host = jdb.get('host', 'localhost')
            db_port = int(jdb.get('port', 5432))
            db_name = jdb.get('db', 'laniakea')
            db_user = jdb.get('user', 'laniakea-user')
            db_password = jdb.get('password', '')

            self._database_url = 'postgresql://{user}:{password}@{host}:{port}/{dbname}'.format(user=db_user,
                                                                                                password=db_password,
                                                                                                host=db_host,
                                                                                                port=db_port,
                                                                                                dbname=db_name)

            self._archive_root_dir = jarchive.get('path', '/nonexistent')
            self._archive_url = jarchive.get('url', '#')
            self._archive_appstream_media_url = jarchive.get('appstream_media_url', 'https://appstream.debian.org/media/pool')

            self._lighthouse_endpoint = jdata.get('LighthouseEndpoint')

            # Synchrotron-specific configuration
            self._synchrotron_sourcekeyrings = []
            if 'Synchrotron' in jdata:
                syncconf = jdata.get('Synchrotron')
                if 'SourceKeyringDir' in syncconf:
                    self._synchrotron_sourcekeyrings = glob(os.path.join(syncconf['SourceKeyringDir'], '*.gpg'))

            # ZCurve
            self._zcurve_keys_basedir = '/etc/laniakea/keys/curve/'

            # Trusted GPG keyrings
            self._trusted_gpg_keyrings = []
            self._trusted_gpg_keyring_dir = jdata.get('TrustedGpgKeyringDir')
            if self._trusted_gpg_keyring_dir:
                self._trusted_gpg_keyrings = glob(os.path.join(self._trusted_gpg_keyring_dir, '*.gpg'))

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
        def archive_appstream_media_url(self) -> str:
            return self._archive_appstream_media_url

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
            except:  # noqa: E722
                pass

            return os.path.join(secrets_dir, '{}-{}_private.sec'.format(platform.node(), module))

        @property
        def zcurve_trusted_certs_dir(self) -> str:
            ''' Retrieve the directory for trusted ZCurve public keys '''

            trusted_dir = os.path.join(self._zcurve_keys_basedir, 'trusted')
            try:
                os.makedirs(trusted_dir, exist_ok=True)
            except:  # noqa: E722
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
