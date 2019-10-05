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
from laniakea.repository import Repository
from laniakea.db import ArchiveSuite, ArchiveComponent, ArchiveArchitecture
from laniakea.utils.gpg import GpgException


def test_repo_local(samplesdir):
    keyrings = [os.path.join(samplesdir, 'gpg', 'keyrings', 'keyring.gpg'),
                os.path.join(samplesdir, 'gpg', 'keyrings', 'other-keyring.gpg')]
    repo_location = os.path.join(samplesdir, 'samplerepo', 'dummy')

    suite = ArchiveSuite('testing')
    component = ArchiveComponent('main')
    arch = ArchiveArchitecture('amd64')
    repo = Repository(repo_location, 'Dummy', trusted_keyrings=[])

    # we have no keyrings set, so this should fail
    with pytest.raises(GpgException):
        src_pkgs = repo.source_packages(suite, component)

    # try again!
    repo = Repository(repo_location, 'Dummy', trusted_keyrings=keyrings)
    src_pkgs = repo.source_packages(suite, component)
    bin_pkgs = repo.binary_packages(suite, component, arch)

    # check packages
    assert len(src_pkgs) == 8
    assert len(bin_pkgs) == 4

    # TODO
