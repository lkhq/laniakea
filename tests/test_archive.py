# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import pytest

from laniakea.db import ArchiveUploader, session_scope
from laniakea.archive import import_key_file_for_uploader

# def test_packages(package_samples):
#    pass


class TestArchive:
    @pytest.fixture(autouse=True)
    def setup(self, localconfig, samples_dir, database):

        gpg_dir = os.path.join(samples_dir, 'packages', 'gpg')

        # create uploader
        with session_scope() as session:
            # Add "A Developer"
            uploader = ArchiveUploader('maint@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_amaintainer.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']

            # Add "Développeur"
            uploader = ArchiveUploader('developpeur@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_developpeur.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['22865D3DA7CF3DE67C1AF9A74014AB2D03010AA9']

            # Add "Snowman"
            uploader = ArchiveUploader('snowman@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_snowman.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']

    def test(self):
        pass
