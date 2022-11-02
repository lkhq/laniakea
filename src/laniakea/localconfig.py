# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import platform
from glob import glob
from dataclasses import field, dataclass

import tomlkit

import laniakea.typing as T
from laniakea.utils import listify


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

    @dataclass
    class LighthouseConfig:
        '''
        Configuration for a Lighthouse server and/or client.
        The configuration is loaded from a :LocalConfig.
        '''

        endpoints_jobs: T.List[str] = field(default_factory=list)
        endpoints_submit: T.List[str] = field(default_factory=list)
        endpoints_publish: T.List[str] = field(default_factory=list)

        servers_jobs: T.List[str] = field(default_factory=list)
        servers_submit: T.List[str] = field(default_factory=list)
        servers_publish: T.List[str] = field(default_factory=list)

    instance = None

    class __LocalConfig:
        def __init__(self, fname=None):
            if not fname:
                fname = get_config_file('base-config.toml')
            self.fname = fname
            if not self.fname:
                raise Exception('Unable to find base configuration (usually in `/etc/laniakea/base-config.toml`')

            cdata = {}
            if os.path.isfile(fname):
                with open(fname) as toml_file:
                    cdata = tomlkit.load(toml_file)

            carchive = cdata.get('Archive')
            if not carchive:
                raise Exception(
                    'No "Archive" configuration found in local config file. Please specify archive details!'
                )

            self._workspace = cdata.get('Workspace')
            if not self._workspace:
                raise Exception(
                    'No "Workspace" directory set in local config file. Please specify a persistent workspace location!'
                )

            # location for various temporary caches that can be deleted at any time
            self._cache_dir = cdata.get('CacheLocation', '/var/tmp/laniakea')

            # the user we run most (archive) commands as
            self._master_user_name = cdata.get('MasterUserName', 'lkmaster')

            jdb = cdata.get('Database', {})
            db_host = jdb.get('host', 'localhost')
            db_port = int(jdb.get('port', 5432))
            db_name = jdb.get('db', 'laniakea')
            db_user = jdb.get('user', 'laniakea-user')
            db_password = jdb.get('password', '')
            self._db_slow_connection = bool(jdb.get('slow_connection', False))

            self._database_url = 'postgresql://{user}:{password}@{host}:{port}/{dbname}'.format(
                user=db_user, password=db_password, host=db_host, port=db_port, dbname=db_name
            )

            self._master_repo_name = carchive.get('master_repo_name', 'master')
            self._archive_root_dir = carchive.get('path', '/nonexistent')
            self._archive_queue_dir = carchive.get('queue_path', os.path.join(self._workspace, 'archive-queues'))
            self._archive_url = carchive.get('url', '#')
            self._archive_appstream_media_url = carchive.get(
                'appstream_media_url', 'https://appstream.debian.org/media/pool'
            )

            self._archive_queue_url = carchive.get('archive_queue_url', 'https://#')

            self._data_import_hooks_dir = os.path.join(self._workspace, 'data-import-hooks')

            self._lighthouse = LocalConfig.LighthouseConfig()
            lhconf = cdata.get('Lighthouse', {})
            lhconf_endpoints = lhconf.get('endpoints', {})
            lhconf_servers = lhconf.get('servers', {})

            self._lighthouse.endpoints_jobs = listify(lhconf_endpoints.get('jobs', 'tcp://*:5570'))
            self._lighthouse.endpoints_submit = listify(lhconf_endpoints.get('submit', 'tcp://*:5571'))
            self._lighthouse.endpoints_publish = listify(lhconf_endpoints.get('publish', 'tcp://*:5572'))

            self._lighthouse.servers_jobs = listify(lhconf_servers.get('jobs', 'tcp://localhost:5570'))
            self._lighthouse.servers_submit = listify(lhconf_servers.get('submit'))
            self._lighthouse.servers_publish = listify(lhconf_servers.get('publish'))

            # Synchrotron-specific configuration
            self._synchrotron_sourcekeyrings = []
            syncconf = cdata.get('Synchrotron')
            if syncconf:
                if 'SourceKeyringDir' in syncconf:
                    self._synchrotron_sourcekeyrings = [
                        v for v in glob(os.path.join(syncconf['SourceKeyringDir'], '*.gpg'))
                    ]

            # ZCurve / Message signing
            self._curve_keys_basedir = cdata.get('CurveKeysDir', os.path.join(self._workspace, 'keys', 'curve'))

            # Trusted GPG keyrings
            self._trusted_gpg_keyrings = []
            self._trusted_gpg_keyring_dir = cdata.get('TrustedGpgKeyringDir')
            if self._trusted_gpg_keyring_dir:
                self._trusted_gpg_keyrings = glob(os.path.join(self._trusted_gpg_keyring_dir, '*.gpg'))

            # Secret GPG Keyring dir
            self._secret_gpg_home_dir = cdata.get(
                'SecretGPGHome', os.path.join(self._workspace, 'keys', 'archive', 's3kr1t')
            )

            # Uploader GPG home dir
            self._uploaders_keyring_dir = cdata.get(
                'UploadersGPGHome', os.path.join(self._workspace, 'keys', 'uploaders')
            )

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
        def database_slow_connection(self) -> bool:
            """Set to True if database server or the connection to it is slow.
            This will make Laniakea set higher timeout values."""
            return self._db_slow_connection

        @property
        def master_user_name(self) -> str:
            """The name of the user we run most (archive) commands as."""
            return self._master_user_name

        @property
        def master_repo_name(self) -> str:
            '''Name of the master repository for this distribution, that (usually) all other repositories are based on.'''
            return self._master_repo_name

        @property
        def archive_root_dir(self) -> str:
            return self._archive_root_dir

        @property
        def archive_queue_dir(self) -> str:
            return self._archive_queue_dir

        @property
        def archive_queue_url(self) -> str:
            """URL where a human user can view the archive queue(s), like the NEW queue"""
            return self._archive_queue_url

        @property
        def archive_flatpak_root_dir(self) -> str:
            return os.path.join(self._archive_root_dir, 'flatpak')

        @property
        def archive_url(self) -> str:
            return self._archive_url

        @property
        def archive_appstream_media_url(self) -> str:
            return self._archive_appstream_media_url

        @property
        def data_import_hooks_dir(self) -> T.PathUnion:
            """Directory with hook scripts to acquire data from external sources."""
            return self._data_import_hooks_dir

        @property
        def lighthouse(self):
            return self._lighthouse

        @property
        def synchrotron_sourcekeyrings(self) -> T.List[str]:
            return self._synchrotron_sourcekeyrings

        def secret_curve_keyfile_for_module(self, module) -> str:
            '''Retrieve the secret ZCurve key filename for a given module name.'''

            secrets_dir = os.path.join(self._curve_keys_basedir, 'secret')
            try:
                os.makedirs(secrets_dir, exist_ok=True)
            except:  # noqa: E722 pylint: disable=W0702
                pass

            fname = os.path.join(secrets_dir, '{}-{}_private.sec'.format(platform.node(), module))

            # if we don't have the specific key, try to fallback to the general key for this machine
            if not os.path.isfile(fname):
                general_key = os.path.join(secrets_dir, '{}-general_private.sec'.format(platform.node()))
                if os.path.isfile(general_key):
                    fname = general_key

            return fname

        @property
        def trusted_curve_keys_dir(self) -> str:
            '''Retrieve the directory for trusted ZCurve public keys'''

            trusted_dir = os.path.join(self._curve_keys_basedir, 'trusted')
            try:
                os.makedirs(trusted_dir, exist_ok=True)
            except:  # noqa: E722 pylint: disable=W0702
                pass

            return trusted_dir

        @property
        def trusted_gpg_keyring_dir(self) -> str:
            return self._trusted_gpg_keyring_dir

        @property
        def trusted_gpg_keyrings(self) -> list:
            return self._trusted_gpg_keyrings

        @property
        def secret_gpg_home_dir(self) -> str:
            return self._secret_gpg_home_dir

        @property
        def uploaders_keyring_dir(self) -> str:
            return self._uploaders_keyring_dir

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
            fname = '/usr/share/laniakea/3rd-party.toml'

        cdata = {}
        if os.path.isfile(fname):
            with open(fname) as toml_file:
                cdata = tomlkit.load(toml_file)

        cspears = cdata.get('Spears', {})
        self.britney_git_repository = cspears.get(
            'britneyGitRepository', 'https://salsa.debian.org/release-team/britney2.git'
        )
