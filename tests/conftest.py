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
    config_json['ZCurveKeysDir'] = os.path.join(test_aux_data_dir, 'keys', 'curve')

    config_fname = os.path.join(test_aux_data_dir, 'base-config.json')
    with open(config_fname, 'w') as f:
        json.dump(config_json, f)

    conf = LocalConfig(config_fname)
    assert conf.cache_dir == '/var/tmp/laniakea'
    assert conf.workspace == '/tmp/test-lkws/'

    assert conf.database_url == 'postgresql://lkdbuser_test:notReallySecret@localhost:5432/laniakea_test'
    assert conf.lighthouse_endpoint == 'tcp://*:5570'

    # Check injected sample certificate directory
    assert conf.zcurve_secret_keyfile_for_module('test').startswith('/tmp/test-lkaux/keys/curve/secret/')
    os.makedirs(conf._zcurve_keys_basedir, exist_ok=True)

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

    # clear database tables sop test function has a pristine database to work with
    with session_scope() as session:
        rows = session.execute('select \'drop table if exists "\' || tablename || \'" cascade;\' from pg_tables where schemaname = \'public\';').fetchall()
        for row in rows:
            sql = row[0]
            session.execute(sql)
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
        suite_us = ArchiveSuite()
        suite_us.name = 'unstable'
        suite_us.repos = [repo]
        suite_us.components = all_components
        suite_us.architectures = all_architectures
        suite_us.accept_uploads = True
        session.add(suite_us)

        # add 'testing' suite
        suite_te = ArchiveSuite()
        suite_te.name = 'testing'
        suite_te.repos = [repo]
        suite_te.components = all_components
        suite_te.architectures = all_architectures
        suite_te.devel_target = True
        session.add(suite_te)

        # add 'experimental' suite
        suite_ex = ArchiveSuite()
        suite_ex.name = 'experimental'
        suite_ex.repos = [repo]
        suite_ex.components = all_components
        suite_ex.architectures = [arch_all, arch_amd64]
        suite_ex.accept_uploads = True
        suite_ex.parent = suite_us
        session.add(suite_ex)

    return db


def generate_zcurve_keys_for_module(sourcesdir, localconfig, mod):
    '''
    Generate new CurveZMQ keys for use by Lighthouse.
    '''
    import subprocess

    sec_dest_fname = localconfig.zcurve_secret_keyfile_for_module(mod)
    if os.path.isfile(sec_dest_fname):
        return
    keytool_exe = os.path.join(sourcesdir, 'keytool', 'keytool.py')
    tmp_basepath = os.path.join('/tmp', 'lksec-{}'.format(random_string()))

    subprocess.run([keytool_exe,
                    'cert-new',
                    '--name', 'Test Key for {}'.format(mod),
                    '--email', 'test-{}@example.org'.format(mod),
                    tmp_basepath], check=True)

    assert os.path.isfile(tmp_basepath + '.key')
    assert os.path.isfile(tmp_basepath + '.key_secret')

    os.remove(tmp_basepath + '.key')
    os.rename(tmp_basepath + '.key_secret', sec_dest_fname)


@pytest.fixture
def make_zcurve_trusted_key(sourcesdir, localconfig):

    def _make_zcurve_trusted_key(name):
        import subprocess

        pub_dest_fname = os.path.join(localconfig.zcurve_trusted_certs_dir, '{}.key'.format(name))
        sec_dest_fname = os.path.join(localconfig.zcurve_trusted_certs_dir, '..', '{}.key_secret'.format(name))
        if os.path.isfile(sec_dest_fname) and os.path.isfile(pub_dest_fname):
            return sec_dest_fname
        keytool_exe = os.path.join(sourcesdir, 'keytool', 'keytool.py')
        tmp_basepath = os.path.join('/tmp', 'lksec-{}'.format(random_string()))

        subprocess.run([keytool_exe,
                        'cert-new',
                        '--name', 'Test Key {}'.format(name),
                        '--email', 'test-{}@example.org'.format(name.replace(' ', '_')),
                        tmp_basepath], check=True)

        assert os.path.isfile(tmp_basepath + '.key')
        assert os.path.isfile(tmp_basepath + '.key_secret')

        os.rename(tmp_basepath + '.key', pub_dest_fname)
        os.rename(tmp_basepath + '.key_secret', sec_dest_fname)

        return sec_dest_fname

    return _make_zcurve_trusted_key


@pytest.fixture(scope='class')
def lighthouse_server(request, sourcesdir, localconfig, database):
    '''
    Spawn a Lighthouse server to communicate with.
    '''
    import time
    import subprocess

    # create new secret key for Lighthouse
    generate_zcurve_keys_for_module(sourcesdir, localconfig, LkModule.LIGHTHOUSE)

    lh_exe = os.path.join(sourcesdir, 'lighthouse', 'lighthouse.py')
    pipe = subprocess.Popen([lh_exe,
                             '--verbose',
                             '--config', localconfig.fname],
                            shell=False,
                            stdout=sys.stdout,
                            stderr=sys.stderr)
    time.sleep(0.5)
    if pipe.poll():
        pytest.fail('Lighthouse failed to start up, check stderr')

    def fin():
        pipe.terminate()
        if not pipe.wait(30):
            pipe.kill()
            pytest.fail('Lighthouse failed to terminate in time')
    request.addfinalizer(fin)
