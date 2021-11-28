# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import subprocess

import pytest

from laniakea.db import (
    ArchiveConfig,
    SourcePackage,
    ArchiveUploader,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import PackageImporter, import_key_file_for_uploader
from laniakea.archive.utils import pool_dir_from_name


def test_utils():
    """Test smaller utility functions"""
    assert pool_dir_from_name('pkgname') == 'pool/p/pkgname'
    assert pool_dir_from_name('libthing') == 'pool/libt/libthing'


class TestArchive:
    @pytest.fixture(autouse=True)
    def setup(self, localconfig, samples_dir, sources_dir, database):

        gpg_dir = os.path.join(samples_dir, 'packages', 'gpg')
        self._lconf = localconfig

        lkadmin_exe = os.path.join(sources_dir, 'lkadmin', 'lk-admin.py')
        subprocess.run(
            [
                lkadmin_exe,
                '--config',
                localconfig.fname,
                'archive',
                'add-from-config',
                os.path.join(samples_dir, 'config', 'archive-config.toml'),
            ],
            check=True,
        )

        with session_scope() as session:
            #
            # check layout
            #

            master_repo_name = self._lconf.master_repo_name
            master_debug_repo_name = '{}-debug'.format(master_repo_name)

            aconfig = session.query(ArchiveConfig).first()
            assert aconfig
            master_repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == master_repo_name).one()
            assert master_repo
            master_debug_repo = (
                session.query(ArchiveRepository).filter(ArchiveRepository.name == master_debug_repo_name).one()
            )
            assert master_debug_repo

            extra_repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'extra').one()
            assert extra_repo

            #
            # create uploaders
            #

            master_repo.uploaders = []
            extra_repo.uploaders = []

            # Add "A Developer"
            uploader = ArchiveUploader('maint@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_amaintainer.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']
            master_repo.uploaders.append(uploader)

            # Add "Développeur"
            uploader = ArchiveUploader('developpeur@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_developpeur.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['22865D3DA7CF3DE67C1AF9A74014AB2D03010AA9']
            master_repo.uploaders.append(uploader)

            # Add "Snowman"
            uploader = ArchiveUploader('snowman@example.com')
            uploader.is_human = True
            import_key_file_for_uploader(uploader, os.path.join(gpg_dir, 'pubkey_snowman.gpg'))
            session.add(uploader)
            assert uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']
            extra_repo.uploaders.append(uploader)

    def test_package_uploads(self, package_samples):
        with session_scope() as session:
            rss = (
                session.query(ArchiveRepoSuiteSettings)
                .filter(
                    ArchiveRepoSuiteSettings.repo.has(name='master'),
                    ArchiveRepoSuiteSettings.suite.has(name='unstable'),
                )
                .one()
            )

            # import a source package directly
            pi = PackageImporter(session, rss)
            pi.keep_source_packages = True
            pi.import_source(os.path.join(package_samples, 'package_0.1-1.dsc'), 'main', skip_new=True)
            session.commit()
            # verify
            assert (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'package',
                    SourcePackage.version == '0.1-1',
                )
                .one()
            )

            # import the corresponding binary package (overrides should be present, so this should work)
            pi.import_binary(os.path.join(package_samples, 'package_0.1-1_all.deb'), 'main')
