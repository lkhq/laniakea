# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import shutil
import subprocess

import pytest

from laniakea import LocalConfig
from laniakea.db import LkModule
from laniakea.utils import run_command, random_string


@pytest.fixture(scope='session')
def samples_dir():
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
def sources_dir():
    '''
    Return the location of Laniakea's sources root directory.
    '''
    from . import source_root

    sources_dir = os.path.join(source_root, 'src')
    if not os.path.isdir(sources_dir):
        raise Exception('Unable to find Laniakea source directory (tried: {})'.format(sources_dir))
    return sources_dir


@pytest.fixture(scope='session', autouse=True)
def localconfig(samples_dir):
    '''
    Retrieve a Laniakea LocalConfig object which is set
    up for testing.
    '''
    import multiprocessing as mp

    import tomlkit

    from laniakea.logging import set_verbose
    from laniakea.utils.misc import find_free_port_nr

    # enable verbose logging for tests
    set_verbose(True)

    test_aux_data_dir = os.path.join('/tmp', 'test-lkaux')
    test_archive_dir = os.path.join('/tmp', 'test-lkarchive')
    if os.path.isdir(test_aux_data_dir):
        shutil.rmtree(test_aux_data_dir)
    os.makedirs(test_aux_data_dir)
    if os.path.isdir(test_archive_dir):
        shutil.rmtree(test_archive_dir)
    os.makedirs(test_archive_dir)

    config_tmpl_fname = os.path.join(samples_dir, 'config', 'base-config.toml')
    with open(config_tmpl_fname, 'r') as f:
        config_toml = tomlkit.load(f)

    # Curve25519 signing/encryption key directory
    config_toml['CurveKeysDir'] = os.path.join(test_aux_data_dir, 'keys', 'curve')
    # set our GPG secret keyring dir
    config_toml['SecretGPGHome'] = os.path.join(samples_dir, 'gpg', 'secret-home')

    # software archive root
    config_toml['Archive']['path'] = test_archive_dir

    # Lighthouse configuration
    lhc = config_toml['Lighthouse']
    lh_jobs_port = find_free_port_nr()
    lh_submit_port = find_free_port_nr()
    lh_publish_port = find_free_port_nr()
    lhc['endpoints']['jobs'] = ['tcp://*:' + str(lh_jobs_port)]
    lhc['endpoints']['submit'] = ['tcp://*:' + str(lh_submit_port)]
    lhc['endpoints']['publish'] = ['tcp://*:' + str(lh_publish_port)]
    lhc['servers']['jobs'] = ['tcp://localhost:' + str(lh_jobs_port)]
    lhc['servers']['submit'] = ['tcp://localhost:' + str(lh_submit_port)]
    lhc['servers']['publish'] = ['tcp://localhost:' + str(lh_publish_port)]

    config_fname = os.path.join(test_aux_data_dir, 'base-config.toml')
    with open(config_fname, 'w') as f:
        tomlkit.dump(config_toml, f)

    conf = LocalConfig(config_fname)
    conf = LocalConfig.instance
    assert conf.cache_dir == '/var/tmp/laniakea'
    assert conf.workspace == '/tmp/test-lkws/'
    if os.path.isdir(conf.workspace):
        shutil.rmtree(conf.workspace)
    os.makedirs(conf.workspace, exist_ok=True)

    assert conf.database_url == 'postgresql://lkdbuser_test:notReallySecret@localhost:5432/laniakea_unittest'

    # Check injected sample certificate directory
    assert conf.secret_curve_keyfile_for_module('test').startswith('/tmp/test-lkaux/keys/curve/secret/')
    os.makedirs(conf._curve_keys_basedir, exist_ok=True)

    # add the trusted keyring with test keys
    conf._synchrotron_sourcekeyrings = []
    conf._synchrotron_sourcekeyrings.append(os.path.join(samples_dir, 'gpg', 'keyrings', 'keyring.gpg'))
    conf._synchrotron_sourcekeyrings.append(os.path.join(samples_dir, 'gpg', 'keyrings', 'other-keyring.gpg'))

    # We do want to use the forkserver method when multiprocessing is in use.
    # It is difficult to find the right place to set that in PyTest, so we set it here to ensure
    # it's called once and as early as possible.
    mp.set_start_method('forkserver')

    return conf


def pgsql_test_available(session_scope):
    """test if PostgreSQL is available with the current configuration."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    try:
        with session_scope() as session:
            session.execute(text('SELECT CURRENT_TIME;'))
    except OperationalError:
        return False
    return True


@pytest.fixture(scope='session')
def postgresql_container():
    """Create & run a PostgreSQL container"""
    import json
    import time
    import timeit

    from . import source_root

    LKPG_IMAGE_TAG = 'lktest_postgres'
    LKPG_CONTAINER_NAME = 'lktest_postgres'
    LKPG_IP = 5432

    class PGSQLContainerInfo:
        container_name: str
        host_ip: str
        pg_host_port: int

        def wait_until_responsive(self, check, timeout, pause, clock=timeit.default_timer):
            """Wait until a service is responsive."""

            ref = time.process_time()
            now = ref
            while (now - ref) < timeout:
                if check():
                    return
                time.sleep(pause)
                now = time.process_time()

            raise Exception("Timeout reached while waiting on service!")

    tests_dir = os.path.join(source_root, 'tests')
    # ensure any previous test container is stopped
    subprocess.run(['podman', 'stop', LKPG_CONTAINER_NAME], check=False)

    # build image
    subprocess.run(
        [
            'podman',
            'build',
            '-t',
            LKPG_IMAGE_TAG,
            '-f',
            os.path.join(tests_dir, 'containers', 'postgres', 'Dockerfile'),
        ],
        check=True,
    )

    # run temporary database container
    subprocess.run(
        [
            'podman',
            'run',
            '-d',
            '-p',
            str(LKPG_IP),
            '--name',
            LKPG_CONTAINER_NAME,
            '--rm',
            LKPG_IMAGE_TAG,
        ],
        check=True,
    )

    # get host IP
    proc = subprocess.run(['podman', 'inspect', LKPG_CONTAINER_NAME], check=True, capture_output=True)

    data = json.loads(proc.stdout)[0]
    ports = data['NetworkSettings']['Ports']
    port_data = ports.get('{}/tcp'.format(LKPG_IP), ports.get('{}/udp'.format(LKPG_IP)))
    if not port_data:
        print('Postgres Container Data Raw:', data, file=sys.stderr)
        raise Exception('Unable to set up PostgreSQL test container: Could not find port settings')

    info = PGSQLContainerInfo()
    info.container_name = LKPG_CONTAINER_NAME
    host_port = port_data[0]['HostPort']
    host_ip = port_data[0]['HostIp']
    if not host_port:
        raise ValueError('Could not detect host port for "%s:%d".' % (LKPG_CONTAINER_NAME, LKPG_IP))
    info.pg_host_port = int(host_port.strip())

    if not host_ip:
        host_ip = '0.0.0.0'
    info.host_ip = host_ip

    yield info

    # tear down container again
    if os.environ.get('LK_TEST_NO_CLEAN', '0') == '0':
        try:
            proc = subprocess.run(
                ['podman', 'stop', LKPG_CONTAINER_NAME], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError:
            print('WARNING: Failed to stop Postgres container:', str(proc.stdout), file=sys.stderr)
            subprocess.run(['podman', 'kill', LKPG_CONTAINER_NAME], check=False)


@pytest.fixture(scope='session')
def create_database(localconfig, postgresql_container):
    '''
    Create a pristine, empty Laniakea database connection.
    This will wipe the global database, so tests using this can
    never run in parallel.
    '''
    import tomlkit

    from laniakea.db import Database, session_scope

    # get IP of our database container
    db_port = postgresql_container.pg_host_port
    podman_ip = postgresql_container.host_ip

    # update database URL to use scratch database in our container
    pgdb_url = 'postgresql://lkdbuser_test:notReallySecret@{}:{}/laniakea_unittest'.format(podman_ip, db_port)
    LocalConfig.instance._database_url = pgdb_url
    assert localconfig.database_url == pgdb_url

    # update the on-disk configuration, we may pass that on to independent modules
    with open(localconfig.fname, 'r') as f:
        config_toml = tomlkit.load(f)
    config_toml['Database']['host'] = podman_ip
    config_toml['Database']['port'] = db_port
    with open(localconfig.fname, 'w') as f:
        tomlkit.dump(config_toml, f)

    # create database factory singleton, if it didn't exist yet
    db = Database(localconfig)

    # wait for the database to become available
    postgresql_container.wait_until_responsive(
        timeout=60.0, pause=0.5, check=lambda: pgsql_test_available(session_scope)
    )

    db.create_tables()
    return db


@pytest.fixture(scope='module')
def database(sources_dir, samples_dir, localconfig, create_database):
    """
    Clear the current activate database and provide a
    pristine, empty database to use.
    """
    from laniakea.db.core import config_set_distro_tag, config_set_project_name

    db = create_database

    # add core configuration data to the database
    config_set_project_name('Test Project')
    config_set_distro_tag('test')

    # create archive configuration for the test suite
    lkadmin_exe = os.path.join(sources_dir, 'lkadmin', 'lk-admin.py')
    subprocess.run(
        [
            lkadmin_exe,
            '--config',
            localconfig.fname,
            'archive',
            'update-from-config',
            os.path.join(samples_dir, 'config', 'archive-config.toml'),
        ],
        check=True,
    )

    yield db

    # drop all our tables and recreate empty ones
    db.drop_tables()
    db.create_tables()


def generate_curve_keys_for_module(sources_dir, localconfig, mod):
    '''
    Generate new CurveZMQ keys for use by Lighthouse.
    '''

    sec_dest_fname = localconfig.secret_curve_keyfile_for_module(mod)
    if os.path.isfile(sec_dest_fname):
        return
    keytool_exe = os.path.join(sources_dir, 'keytool', 'keytool.py')

    key_id = 'test-{}_{}'.format(mod, random_string(4))
    tmp_path = '/tmp'
    key_basepath = os.path.join(tmp_path, key_id)

    subprocess.run(
        [
            keytool_exe,
            'key-new',
            '--id',
            key_id,
            '--name',
            'Test Key for {}'.format(mod),
            '--email',
            'test-{}@example.org'.format(mod),
            tmp_path,
        ],
        check=True,
    )

    assert os.path.isfile(key_basepath + '.key')
    assert os.path.isfile(key_basepath + '.key_secret')

    os.remove(key_basepath + '.key')
    os.rename(key_basepath + '.key_secret', sec_dest_fname)


@pytest.fixture
def make_curve_trusted_key(sources_dir, localconfig):
    def _make_curve_trusted_key(name):
        pub_dest_fname = os.path.join(localconfig.trusted_curve_keys_dir, '{}.key'.format(name))
        sec_dest_fname = os.path.join(localconfig.trusted_curve_keys_dir, '..', '{}.key_secret'.format(name))
        if os.path.isfile(sec_dest_fname) and os.path.isfile(pub_dest_fname):
            return sec_dest_fname
        keytool_exe = os.path.join(sources_dir, 'keytool', 'keytool.py')

        key_id = name.replace(' ', '_')
        tmp_path = '/tmp'
        key_basepath = os.path.join(tmp_path, key_id)

        subprocess.run(
            [
                keytool_exe,
                'key-new',
                '--id',
                key_id,
                '--name',
                'Test Key {}'.format(name),
                '--email',
                'test-{}@example.org'.format(key_id),
                tmp_path,
            ],
            check=True,
        )

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
        def __init__(self, sources_dir, lconf):
            self._sources_dir = sources_dir
            self._lconf = lconf
            self._pipe = None

        def start(self):
            import time

            # ensure we are not running anymore, in case we were before
            self.terminate()

            # create new secret key for Lighthouse
            generate_curve_keys_for_module(self._sources_dir, self._lconf, LkModule.LIGHTHOUSE)

            lh_exe = os.path.join(self._sources_dir, 'lighthouse', 'lighthouse-server')
            self._pipe = subprocess.Popen(
                [lh_exe, '--verbose', '--config', self._lconf.fname], shell=False, stdout=sys.stdout, stderr=sys.stderr
            )
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

    def __init__(self, sources_dir, lconf):
        if not LighthouseServer.instance:
            LighthouseServer.instance = LighthouseServer.__LhServer(sources_dir, lconf)

    def __getattr__(self, name):
        return getattr(self.instance, name)


@pytest.fixture(scope='class')
def lighthouse_server(request, sources_dir, localconfig, database):
    '''
    Spawn a Lighthouse server to communicate with.
    '''

    lhs = LighthouseServer(sources_dir, localconfig)
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
def import_sample_packages(package_samples, database):
    """
    Ensure sample packages are imported into the database.
    """
    from glob import iglob
    from fnmatch import fnmatch

    from laniakea.db import NewPolicy, BinaryPackage, SourcePackage, session_scope
    from laniakea.archive import PackageImporter
    from laniakea.archive.utils import repo_suite_settings_for
    from laniakea.archive.manage import remove_source_package

    spkg_ids = []
    bpkg_ids = []
    # import everything we have
    with session_scope() as session:
        rss = repo_suite_settings_for(session, 'master', 'unstable')

        # import a source package directly
        pi = PackageImporter(session, rss)
        pi.keep_source_packages = True
        pi.prefer_hardlinks = True

        for dsc_fname in sorted(iglob(os.path.join(package_samples, '*.dsc'))):
            if dsc_fname.endswith('~exp.dsc'):
                continue
            spkg, _ = pi.import_source(dsc_fname, 'main', new_policy=NewPolicy.NEVER_NEW, ignore_version_check=True)
            spkg_ids.append(spkg.uuid)
            assert spkg

        for deb_fname in iglob(os.path.join(package_samples, '*.deb')):
            if fnmatch(deb_fname, '*~exp_*.deb'):
                continue
            bpkg = pi.import_binary(deb_fname, ignore_version_check=True)
            assert bpkg
            bpkg_ids.append(bpkg.uuid)
        for udeb_fname in iglob(os.path.join(package_samples, '*.udeb')):
            bpkg = pi.import_binary(udeb_fname, ignore_version_check=True)
            assert bpkg
            bpkg_ids.append(bpkg.uuid)

    yield

    # cleanup
    with session_scope() as session:
        rss = repo_suite_settings_for(session, 'master', 'unstable')

        for spkg_uuid in spkg_ids:
            spkg = session.query(SourcePackage).filter(SourcePackage.uuid == spkg_uuid).one()
            assert remove_source_package(session, rss, spkg)
        for bpkg_uuid in bpkg_ids:
            bpkg = session.query(BinaryPackage).filter(BinaryPackage.uuid == bpkg_uuid).one_or_none()
            if not bpkg:
                # package might have already been removed
                continue
            pytest.fail(
                'Binary package "%s" has not been removed, even though it should have been dropped with its source package.'
                % str(bpkg)
            )


@pytest.fixture(scope='session')
def package_samples(samples_dir):
    '''
    Fixture responsible for building a set of test packages and cleaning them up once we
    are done with running tests.
    '''

    pkg_dir = os.path.join(samples_dir, 'packages')
    if not os.path.isfile(os.path.join(pkg_dir, 'package_0.1-1_all.deb')):
        subprocess.run(['make'], cwd=pkg_dir, check=True)
    yield pkg_dir
    if os.environ.get('LK_TEST_NO_CLEAN', '0') == '0':
        subprocess.run(['make', 'clean'], cwd=pkg_dir, check=True)


@pytest.fixture(scope='session')
def host_deb_arch():
    out, err, ret = run_command(['dpkg', '--print-architecture'])
    assert ret == 0
    arch = out.strip()
    assert arch
    yield arch
