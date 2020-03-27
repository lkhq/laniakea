# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2020 Matthias Klumpp <matthias@tenstral.net>
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

from tempfile import TemporaryDirectory
from laniakea.db import FlatpakRepository
from laniakea.flatpak_util import FlatpakUtil


def test_flatpak_init_repo(localconfig, samplesdir):
    ''' Check if we can create an empty Flatpak repo '''

    repo = FlatpakRepository('laniakea_test')
    repo.collection_id = 'org.example.LaniakeaUnittest'
    repo.title = 'Laniakea Unit Test Repository'
    repo.comment = 'Just a test'
    repo.url_homepage = 'https://tanglu.org'
    repo.gpg_key_id = '8BB746C63FF5346326C19ABDEFD8BD07D224478F'
    repo.allowed_branches = ['stable', 'testing', 'edge']
    repo.default_branch = 'stable'

    with TemporaryDirectory(prefix='lkunittest-') as tmpdir:
        fputil = FlatpakUtil()
        fputil.init_repo(repo, tmpdir)
