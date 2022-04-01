# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import subprocess

import pytest

from laniakea.db import (
    NewPolicy,
    ArchiveSuite,
    ArchiveConfig,
    BinaryPackage,
    SourcePackage,
    ArchiveUploader,
    ArchiveRepository,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import (
    UploadHandler,
    PackageImporter,
    ArchiveImportError,
    remove_source_package,
    import_key_file_for_uploader,
)
from laniakea.utils.gpg import GpgException
from lkarchive.process_new import newqueue_accept, newqueue_reject
from laniakea.archive.utils import (
    check_overrides_source,
    find_package_in_new_queue,
    pool_dir_from_name_component,
)


def test_utils():
    """Test smaller utility functions"""
    assert pool_dir_from_name_component('pkgname', 'main') == 'pool/main/p/pkgname'
    assert pool_dir_from_name_component('libthing', 'main') == 'pool/main/libt/libthing'


class TestParseChanges:
    @pytest.fixture(autouse=True)
    def setup(self, samples_dir, sources_dir, database):
        self._changes_dir = os.path.join(samples_dir, 'changes')

    def parse(self, filename, **kwargs):
        from laniakea.archive.changes import parse_changes

        return parse_changes(os.path.join(self._changes_dir, filename), require_signature=False, **kwargs)

    def test_parse_changes(self, samples_dir):
        with pytest.raises(GpgException) as einfo:
            self.parse('1.changes')
        assert 'No data.' in str(einfo.value)

        changes = self.parse('2.changes')
        binaries = changes.changes['binary']
        assert 'krb5-ftpd' in binaries.split()
        assert changes.source_name == 'krb5'
        assert changes.distributions == ['unstable']
        assert changes.architectures == ['m68k']

        for filename in ('valid', 'bogus-pre', 'bogus-post'):
            changes = self.parse('{}.changes'.format(filename))
            assert not changes.changes.get('you')


class TestArchive:
    @pytest.fixture(autouse=True)
    def setup(self, localconfig, samples_dir, sources_dir, database, host_deb_arch):

        gpg_dir = os.path.join(samples_dir, 'packages', 'gpg')
        self._lconf = localconfig
        self._archive_root = self._lconf.archive_root_dir
        self._queue_root = self._lconf.archive_queue_dir
        self._host_arch = host_deb_arch

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

        # use
        yield

        # cleanup
        with session_scope() as session:
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'maint@example.com').one()
            session.delete(uploader)
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'developpeur@example.com').one()
            session.delete(uploader)
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'snowman@example.com').one()
            session.delete(uploader)

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
            pi.import_source(os.path.join(package_samples, 'package_0.1-1.dsc'), 'main', new_policy=NewPolicy.NEVER_NEW)
            session.commit()
            # verify
            assert (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'package',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one()
            )
            assert os.path.isfile(
                os.path.join(self._archive_root, 'master', 'pool', 'main', 'p', 'package', 'package_0.1-1.dsc')
            )

            # import the corresponding binary package (overrides should be present, so this should work)
            pi.import_binary(os.path.join(package_samples, 'package_0.1-1_all.deb'), 'main')
            # verify
            assert (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'package',
                    BinaryPackage.version == '0.1-1',
                )
                .one()
            )
            assert os.path.isfile(
                os.path.join(self._archive_root, 'master', 'pool', 'main', 'p', 'package', 'package_0.1-1_all.deb')
            )

            # try importing a binary that does not have overrides set
            with pytest.raises(ArchiveImportError) as einfo:
                pi.import_binary(os.path.join(package_samples, 'snowman_0.1-1_all.deb'), 'main')
            assert 'Could not find corresponding source package.' in str(einfo.value)
            session.commit()
            assert (
                not session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'snowman',
                    BinaryPackage.version == '0.1-1',
                )
                .first()
            )
            assert not os.path.isfile(
                os.path.join(self._archive_root, 'master', 'pool', 's', 'snowman', 'snowman_0.1-1_all.deb')
            )

            # add source package to NEW
            pi.import_source(os.path.join(package_samples, 'snowman_0.1-1.dsc'), 'main')
            session.commit()
            assert os.path.isfile(
                os.path.join(self._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')
            )
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'snowman',
                    SourcePackage.version == '0.1-1',
                )
                .one()
            )
            # package must not be in any suites
            assert not spkg.suites

            # try importing that binary again
            pi.import_binary(os.path.join(package_samples, 'snowman_0.1-1_all.deb'), 'main')
            assert os.path.isfile(
                os.path.join(self._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1_all.deb')
            )
            assert (
                not session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'snowman',
                    BinaryPackage.version == '0.1-1',
                )
                .first()
            )
            session.commit()

            # importing two packages which are already in NEW should work
            pi.import_source(
                os.path.join(package_samples, 'snowman_0.1-1.dsc'), 'main', new_policy=NewPolicy.ALWAYS_NEW
            )
            pi.import_binary(os.path.join(package_samples, 'snowman_0.1-1_all.deb'), 'main')
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'snowman',
                    SourcePackage.version == '0.1-1',
                )
                .one()
            )
            assert not spkg.suites
            nq_entry = find_package_in_new_queue(session, rss, spkg)
            assert nq_entry

            # accept the package from the NEW queue
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 1
            newqueue_accept(session, rss, spkg, missing_overrides)
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.suites.any(ArchiveSuite.name == rss.suite.name),
                    SourcePackage.name == 'snowman',
                    SourcePackage.version == '0.1-1',
                )
                .one_or_none()
            )
            assert spkg
            assert not os.path.isfile(
                os.path.join(self._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')
            )
            assert os.path.join(self._archive_root, 'master', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')

            # test processing an actual upload from a changes file
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            uh = UploadHandler(session, repo)
            uh.keep_source_packages = True

            success, uploader, error = uh.process_changes(
                os.path.join(package_samples, 'package_0.2-1_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            assert uploader.email == 'snowman@example.com'
            assert uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']

            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'package',
                    SourcePackage.version == '0.2-1',
                    SourcePackage.component.has(name='main'),
                    SourcePackage.suites.any(ArchiveSuite.name == 'unstable'),
                )
                .one_or_none()
            )
            assert spkg

            # try to import the same thing again and watch it fail
            success, uploader, error = uh.process_changes(
                os.path.join(package_samples, 'package_0.2-1_%s.changes' % self._host_arch)
            )
            assert (
                error
                == 'We have already seen higher or equal version "0.2-1" of source package "package" in repository "master" before.'
            )
            assert not success
            assert uploader.email == 'snowman@example.com'
            assert uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']

            # try importing a non-free package, this thing should end up in NEW
            success, uploader, error = uh.process_changes(
                os.path.join(package_samples, 'nonfree-package_0.1-1_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            assert uploader.email == 'maint@example.com'
            assert uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']

            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'nonfree-package',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.component.has(name='non-free'),
                    ~SourcePackage.suites.any(),
                )
                .one_or_none()
            )
            assert spkg  # should be registered, but should not have suite associations

            nonfreepkg_pool_subdir = os.path.join(
                'pool', 'non-free', 'n', 'nonfree-package', 'nonfree-package_0.1-1.dsc'
            )
            assert os.path.isfile(os.path.join(self._queue_root, 'master', 'new', nonfreepkg_pool_subdir))

            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'nonfree-package',
                    BinaryPackage.version == '0.1-1',
                    BinaryPackage.component.has(name='non-free'),
                )
                .one_or_none()
            )
            assert not bpkg  # should not be in here, will be in NEW instead
            assert os.path.isfile(
                os.path.join(
                    self._queue_root,
                    'master',
                    'new',
                    'pool',
                    'non-free',
                    'n',
                    'nonfree-package',
                    'nonfree-package_0.1-1_all.deb',
                )
            )

            # accept the non-free package from the NEW queue
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 1
            newqueue_accept(session, rss, spkg, missing_overrides)
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.suites.any(ArchiveSuite.name == rss.suite.name),
                    SourcePackage.name == 'nonfree-package',
                    SourcePackage.version == '0.1-1',
                )
                .one_or_none()
            )
            assert spkg
            assert not os.path.isfile(os.path.join(self._queue_root, 'master', 'new', nonfreepkg_pool_subdir))
            assert os.path.join(self._archive_root, 'master', nonfreepkg_pool_subdir)

            # process another upload, and reject it
            success, uploader, error = uh.process_changes(
                os.path.join(package_samples, 'pkgnew_0.1-1_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            assert uploader.email == 'maint@example.com'
            assert uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'pkgnew',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.component.has(name='main'),
                    ~SourcePackage.suites.any(),
                )
                .one_or_none()
            )
            assert spkg

            pkg_pool_subdir = os.path.join('pool', 'main', 'p', 'pkgnew', 'pkgnew_0.1-1.dsc')
            assert os.path.isfile(os.path.join(self._queue_root, 'master', 'new', pkg_pool_subdir))
            assert not os.path.isfile(os.path.join(self._archive_root, 'master', pkg_pool_subdir))

            newqueue_reject(session, rss, spkg)
            assert not os.path.isfile(os.path.join(self._queue_root, 'master', 'new', pkg_pool_subdir))
            assert not os.path.isfile(os.path.join(self._archive_root, 'master', pkg_pool_subdir))
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'pkgnew',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.component.has(name='main'),
                    ~SourcePackage.suites.any(),
                )
                .one_or_none()
            )
            assert not spkg

            # process two uploads adding multiple versions
            # pkgnew 0.1-1
            success, _, error = uh.process_changes(
                os.path.join(package_samples, 'pkgnew_0.1-1_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.name == 'pkgnew', SourcePackage.version == '0.1-1')
                .one()
            )
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 4
            newqueue_accept(session, rss, spkg, missing_overrides)
            session.flush()

            # pkgnew 0.1-2
            success, _, error = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-2_source.changes'))
            assert error == None
            assert success
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.name == 'pkgnew', SourcePackage.version == '0.1-2')
                .one()
            )
            missing_overrides = check_overrides_source(session, rss, spkg)
            # this package has 4 new binary packages
            assert len(missing_overrides) == 4
            newqueue_accept(session, rss, spkg, missing_overrides)

            # add the missing binaries
            success, _, error = uh.process_changes(
                os.path.join(package_samples, 'pkgnew_0.1-2_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'pkg-any1',
                    BinaryPackage.version == '0.1-2',
                    BinaryPackage.component.has(name='main'),
                    SourcePackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert bpkg

            # pkgnew 0.1-3
            success, _, error = uh.process_changes(
                os.path.join(package_samples, 'pkgnew_0.1-3_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.name == 'pkgnew', SourcePackage.version == '0.1-3')
                .one()
            )
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 0
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'pkg-all3',
                    BinaryPackage.version == '0.1-3',
                    BinaryPackage.component.has(name='main'),
                    SourcePackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert bpkg

        # the NEW queue should be completely empty now, for all suites and repos
        queue_entries_count = session.query(ArchiveQueueNewEntry).count()
        assert queue_entries_count == 0

    def test_package_delete(self, package_samples):
        with session_scope() as session:
            rss = (
                session.query(ArchiveRepoSuiteSettings)
                .filter(
                    ArchiveRepoSuiteSettings.repo.has(name='master'),
                    ArchiveRepoSuiteSettings.suite.has(name='unstable'),
                )
                .one()
            )
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            uh = UploadHandler(session, repo)
            uh.keep_source_packages = True

            # add package and verify that is exists in the archive
            success, uploader, error = uh.process_changes(
                os.path.join(package_samples, 'grave_0.1-1_%s.changes' % self._host_arch)
            )
            assert error == None
            assert success
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'grave',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.component.has(name='main'),
                )
                .one_or_none()
            )
            assert spkg
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 1
            assert spkg.suites == []
            newqueue_accept(session, rss, spkg, missing_overrides, include_binaries=True)
            assert spkg.suites[0].name == 'unstable'
            assert os.path.isfile(os.path.join(self._archive_root, 'master', spkg.directory, 'grave_0.1-1.dsc'))
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'grave',
                    BinaryPackage.version == '0.1-1',
                    BinaryPackage.component.has(name='main'),
                    BinaryPackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert bpkg
            assert os.path.isfile(os.path.join(self._archive_root, 'master', spkg.directory, 'grave_0.1-1_all.deb'))

            # now delete the package again and check that it is gone
            spkg_directory = spkg.directory
            remove_source_package(session, rss, spkg)
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'grave',
                    SourcePackage.version == '0.1-1',
                    SourcePackage.component.has(name='main'),
                )
                .one_or_none()
            )
            assert not spkg
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'grave',
                    BinaryPackage.version == '0.1-1',
                    BinaryPackage.component.has(name='main'),
                    BinaryPackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert not bpkg
            assert not os.path.isdir(os.path.join(self._archive_root, 'master', spkg_directory))

    def test_publish(self):
        from lkarchive.publish import publish_repo_dists

        with session_scope() as session:
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            publish_repo_dists(session, repo)
