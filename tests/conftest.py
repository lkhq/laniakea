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
import pytest
from laniakea import LocalConfig
from laniakea.logging import set_verbose


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


@pytest.fixture(scope='session', autouse=True)
def localconfig(samplesdir):
    '''
    Retrieve a Laniakea LocalConfig object which is set
    up for testing.
    '''
    conf = LocalConfig(os.path.join(samplesdir, 'config', 'base-config.json'))

    assert conf.cache_dir == '/var/tmp/laniakea'
    assert conf.workspace == '/tmp/test-lkws/'

    assert conf.database_url == 'postgresql://lkdbuser_test:notReallySecret@localhost:5432/laniakea_test'
    assert conf.lighthouse_endpoint == 'tcp://*:5570'

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
