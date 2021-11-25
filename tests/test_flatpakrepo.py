# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

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
