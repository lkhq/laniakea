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
    from laniakea.db import Database
    db = Database(localconfig)

    # TODO: Clear database contents so tests have a pristine database
    # to work with.

    return db
