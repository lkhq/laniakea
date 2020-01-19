# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Matthias Klumpp <matthias@tenstral.net>
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
import sys
import pytest
from laniakea import LocalConfig
from laniakea.logging import set_verbose
from laniakea.utils import random_string
from laniakea.db import LkModule


# unconditionally enable verbose mode
set_verbose(True)


@pytest.fixture(scope='session')
def samplesdir():
    '''
    Fixture responsible for returning the location of static
    test data the test may use.
    '''
    from . import source_root

    samples_dir = os.path.join(source_root, 'tests', 'test_data')
    if not os.path.isdir(samples_dir):
        raise Exception('Unable to find test samples directory in {}'.format(samples_dir))
    return samples_dir


@pytest.fixture(scope='session')
def sourcesdir():
    '''
    Return the location of Laniakea's sources root directory.
    '''
    from . import source_root

    sources_dir = os.path.join(source_root, 'src')
    if not os.path.isdir(sources_dir):
        raise Exception('Unable to find Laniakea source directory (tried: {})'.format(sources_dir))
    return sources_dir


@pytest.fixture(scope='session', autouse=True)
def localconfig(samplesdir):
    '''
    Retrieve a Laniakea LocalConfig object which is set
    up for testing.
    '''
    import json

    test_aux_data_dir = os.path.join('/tmp', 'test-lkaux')
    if os.path.isdir(test_aux_data_dir):
        from shutil import rmtree
        rmtree(test_aux_data_dir)
    os.makedirs(test_aux_data_dir)

    config_tmpl_fname = os.path.join(samplesdir, 'config', 'base-config.json')
    with open(config_tmpl_fname, 'r') as f:
        config_json = json.load(f)

    config_json['CurveKeysDir'] = os.path.join(test_aux_data_dir, 'keys', 'curve')
    config_json['Archive']['path'] = os.path.join(samplesdir, 'samplerepo', 'dummy')

    config_fname = os.path.join(test_aux_data_dir, 'base-config.json')
    with open(config_fname, 'w') as f:
        json.dump(config_json, f)

    conf = LocalConfig(config_fname)
    assert conf.cache_dir == '/var/tmp/laniakea'
    assert conf.workspace == '/tmp/test-lkws/'

    assert conf.database_url == 'postgresql://lkdbuser_test:notReallySecret@localhost:5432/laniakea_unittest'
    assert conf.lighthouse.endpoints_jobs == ['tcp://*:5570']
    assert conf.lighthouse.endpoints_submit == ['tcp://*:5571']
    assert conf.lighthouse.endpoints_publish == ['tcp://*:5572']
    assert conf.lighthouse.servers_jobs == ['tcp://localhost:5570']
    assert conf.lighthouse.servers_submit == ['tcp://localhost:5571']
    assert conf.lighthouse.servers_publish == ['tcp://localhost:5572']

    # Check injected sample certificate directory
    assert conf.secret_curve_keyfile_for_module('test').startswith('/tmp/test-lkaux/keys/curve/secret/')
    os.makedirs(conf._curve_keys_basedir, exist_ok=True)

    # add the trusted keyring with test keys
    conf.trusted_gpg_keyrings = []
    conf.trusted_gpg_keyrings.append(os.path.join(samplesdir, 'gpg', 'keyrings', 'keyring.gpg'))
    conf.trusted_gpg_keyrings.append(os.path.join(samplesdir, 'gpg', 'keyrings', 'other-keyring.gpg'))

    return conf


@pytest.fixture(scope='class')
def database(localconfig):
    '''
    Retrieve a pristine, empty Laniakea database connection.
    This will wipe the global database, so tests using this can
    never run in parallel.
    '''
    from laniakea.db import Database, session_scope, ArchiveRepository, ArchiveSuite, \
        ArchiveComponent, ArchiveArchitecture
    from laniakea.db.core import config_set_project_name, config_set_distro_tag
    db = Database(localconfig)  # create singleton, if it didn't exist yet

    # clear database tables so test function has a pristine database to work with
    with session_scope() as session:
        session.execute('DROP owned BY lkdbuser_test;')
    db.downgrade('base')
    db.create_tables()

    # add core configuration data to the database
    config_set_project_name('Test Project')
    config_set_distro_tag('test')
    with session_scope() as session:
        # master repository, currently the only one we support
        repo = ArchiveRepository('master')
        session.add(repo)

        # components
        acpt_main = ArchiveComponent('main')
        acpt_contrib = ArchiveComponent('contrib')
        acpt_nonfree = ArchiveComponent('non-free')
        acpt_contrib.parent_component = acpt_main
        acpt_nonfree.parent_component = acpt_main

        all_components = [acpt_main, acpt_contrib, acpt_nonfree]
        session.add_all(all_components)

        # architectures
        arch_all = ArchiveArchitecture('all')
        arch_amd64 = ArchiveArchitecture('amd64')
        arch_arm64 = ArchiveArchitecture('arm64')

        all_architectures = [arch_all, arch_amd64, arch_arm64]
        session.add_all(all_architectures)

        # add 'unstable' suite
        suite_us = ArchiveSuite('unstable')
        suite_us.repos = [repo]
        suite_us.components = all_components
        suite_us.architectures = all_architectures
        suite_us.accept_uploads = True
        session.add(suite_us)

        # add 'testing' suite
        suite_te = ArchiveSuite('testing')
        suite_te.repos = [repo]
        suite_te.components = all_components
        suite_te.architectures = all_architectures
        suite_te.devel_target = True
        session.add(suite_te)

        # add 'experimental' suite
        suite_ex = ArchiveSuite('experimental')
        suite_ex.repos = [repo]
        suite_ex.components = all_components
        suite_ex.architectures = [arch_all, arch_amd64]
        suite_ex.accept_uploads = True
        suite_ex.parent = suite_us
        session.add(suite_ex)

    return db


def generate_curve_keys_for_module(sourcesdir, localconfig, mod):
    '''
    Generate new CurveZMQ keys for use by Lighthouse.
    '''
    import subprocess

    sec_dest_fname = localconfig.secret_curve_keyfile_for_module(mod)
    if os.path.isfile(sec_dest_fname):
        return
    keytool_exe = os.path.join(sourcesdir, 'keytool', 'keytool.py')

    key_id = 'test-{}_{}'.format(mod, random_string(4))
    tmp_path = '/tmp'
    key_basepath = os.path.join(tmp_path, key_id)

    subprocess.run([keytool_exe,
                    'key-new',
                    '--id', key_id,
                    '--name', 'Test Key for {}'.format(mod),
                    '--email', 'test-{}@example.org'.format(mod),
                    tmp_path], check=True)

    assert os.path.isfile(key_basepath + '.key')
    assert os.path.isfile(key_basepath + '.key_secret')

    os.remove(key_basepath + '.key')
    os.rename(key_basepath + '.key_secret', sec_dest_fname)


@pytest.fixture
def make_curve_trusted_key(sourcesdir, localconfig):

    def _make_curve_trusted_key(name):
        import subprocess

        pub_dest_fname = os.path.join(localconfig.trusted_curve_keys_dir, '{}.key'.format(name))
        sec_dest_fname = os.path.join(localconfig.trusted_curve_keys_dir, '..', '{}.key_secret'.format(name))
        if os.path.isfile(sec_dest_fname) and os.path.isfile(pub_dest_fname):
            return sec_dest_fname
        keytool_exe = os.path.join(sourcesdir, 'keytool', 'keytool.py')

        key_id = name.replace(' ', '_')
        tmp_path = '/tmp'
        key_basepath = os.path.join(tmp_path, key_id)

        subprocess.run([keytool_exe,
                        'key-new',
                        '--id', key_id,
                        '--name', 'Test Key {}'.format(name),
                        '--email', 'test-{}@example.org'.format(key_id),
                        tmp_path], check=True)

        assert os.path.isfile(key_basepath + '.key')
        assert os.path.isfile(key_basepath + '.key_secret')

        os.rename(key_basepath + '.key', pub_dest_fname)
        os.rename(key_basepath + '.key_secret', sec_dest_fname)

        return sec_dest_fname

    return _make_curve_trusted_key


class LighthouseServer:
    '''
    Helper class to manage running background Lighthouse instances for tests.
    '''

    instance = None

    class __LhServer:
        def __init__(self, sourcesdir, lconf):
            self._sources_dir = sourcesdir
            self._lconf = lconf
            self._pipe = None

        def start(self):
            import time
            import subprocess

            # ensure we are not running anymore, in case we were before
            self.terminate()

            # create new secret key for Lighthouse
            generate_curve_keys_for_module(self._sources_dir, self._lconf, LkModule.LIGHTHOUSE)

            lh_exe = os.path.join(self._sources_dir, 'lighthouse', 'lighthouse.py')
            self._pipe = subprocess.Popen([lh_exe,
                                           '--verbose',
                                           '--config', self._lconf.fname],
                                          shell=False,
                                          stdout=sys.stdout,
                                          stderr=sys.stderr)
            time.sleep(0.5)
            if self._pipe.poll():
                pytest.fail('Lighthouse failed to start up, check stderr')

        def terminate(self):
            if not self._pipe:
                return
            self._pipe.terminate()
            if not self._pipe.wait(20):
                self._pipe.kill()
                pytest.fail('Lighthouse failed to terminate in time')
            self._pipe = None

    def __init__(self, sourcesdir, lconf):
        if not LighthouseServer.instance:
            LighthouseServer.instance = LighthouseServer.__LhServer(sourcesdir, lconf)

    def __getattr__(self, name):
        return getattr(self.instance, name)


@pytest.fixture(scope='class')
def lighthouse_server(request, sourcesdir, localconfig, database):
    '''
    Spawn a Lighthouse server to communicate with.
    '''

    lhs = LighthouseServer(sourcesdir, localconfig)
    yield lhs
    lhs.terminate()


@pytest.fixture
def new_zmq_curve_socket(request):
    '''
    Create an encrypted ZeroMQ client connection to a Lighthouse server.
    '''

    def _zmq_curve_socket(kind, location, server_cert_fname, client_secret_file):
        import zmq
        import zmq.auth

        if not kind:
            kind = zmq.DEALER

        zctx = zmq.Context()
        sock = zctx.socket(kind)

        # set server certificate
        server_public, _ = zmq.auth.load_certificate(server_cert_fname)
        sock.curve_serverkey = server_public

        # set client certificate
        client_public, client_secret = zmq.auth.load_certificate(client_secret_file)
        sock.curve_secretkey = client_secret
        sock.curve_publickey = client_public

        # connect
        sock.connect(location)

        def fin():
            sock.close()
        request.addfinalizer(fin)

        return sock

    return _zmq_curve_socket


@pytest.fixture(scope='class')
def import_package_data(request, sourcesdir, localconfig, database):
    '''
    Retrieve a pristine, empty Laniakea database connection.
    This will wipe the global database, so tests using this can
    never run in parallel.
    '''
    import subprocess

    dataimport_exe = os.path.join(sourcesdir, 'dataimport', 'dataimport.py')
    suite_name = getattr(request.module, 'dataimport_suite', 'unstable')

    subprocess.run([dataimport_exe,
                    '--config', localconfig.fname,
                    'repo', suite_name], check=True)
