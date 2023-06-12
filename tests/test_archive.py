# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil

import pytest

from laniakea.db import (
    NewPolicy,
    ArchiveSuite,
    ArchiveConfig,
    BinaryPackage,
    SourcePackage,
    ArchiveSection,
    ArchiveUploader,
    ArchiveRepository,
    SoftwareComponent,
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
from laniakea.localconfig import LintianConfig
from lkarchive.data_import import import_heidi_result
from lkarchive.process_new import newqueue_accept, newqueue_reject
from laniakea.archive.utils import (
    re_file_orig,
    lintian_check,
    check_overrides_source,
    repo_suite_settings_for,
    find_package_in_new_queue,
    pool_dir_from_name_component,
    repo_suite_settings_for_debug,
)
from laniakea.archive.manage import expire_superseded


def test_utils():
    """Test smaller utility functions"""
    assert pool_dir_from_name_component('pkgname', 'main') == 'pool/main/p/pkgname'
    assert pool_dir_from_name_component('libthing', 'main') == 'pool/main/libt/libthing'


class TestParseChanges:
    @pytest.fixture(autouse=True)
    def setup(self, samples_dir, sources_dir):
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
    @staticmethod
    @pytest.fixture(scope='class')
    def ctx(localconfig, samples_dir, database, host_deb_arch):
        """Context and global, shared state for all functions in this module."""

        class Context:
            pass

        ctx = Context()
        gpg_dir = os.path.join(samples_dir, 'packages', 'gpg')
        ctx._lconf = localconfig
        ctx._archive_root = ctx._lconf.archive_root_dir
        ctx._queue_root = ctx._lconf.archive_queue_dir
        ctx._host_arch = host_deb_arch

        with session_scope() as session:
            #
            # check layout
            #

            master_repo_name = ctx._lconf.master_repo_name
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
        yield ctx

        # cleanup
        with session_scope() as session:
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'maint@example.com').one()
            session.delete(uploader)
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'developpeur@example.com').one()
            session.delete(uploader)
            uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == 'snowman@example.com').one()
            session.delete(uploader)

            # remove all packages from our mock archive (binary packages are implicitly dropped)
            fnames = []
            for rss in session.query(ArchiveRepoSuiteSettings).all():
                spkgs = (
                    session.query(SourcePackage)
                    .filter(SourcePackage.repo_id == rss.repo_id)
                    .filter(SourcePackage.suites.any(id=rss.suite_id))
                    .all()
                )
                for spkg in spkgs:
                    if len(spkg.suites) <= 1:
                        for file in spkg.files:
                            fnames.append(file.fname)
                            assert os.path.isfile(os.path.join(ctx._archive_root, rss.repo.name, file.fname))

                    assert remove_source_package(session, rss, spkg)

                queue_entries = (
                    session.query(ArchiveQueueNewEntry)
                    .filter(
                        ArchiveQueueNewEntry.destination_id == rss.suite_id,
                        ArchiveQueueNewEntry.package.has(repo_id=rss.repo_id),
                    )
                    .all()
                )

                for entry in queue_entries:
                    spkg = entry.package
                    newqueue_reject(session, rss, spkg)

                # immediately expire anything that has been marked as deleted
                expire_superseded(session, rss, retention_days=0)

            # ensure source package files are really gone
            for repo in session.query(ArchiveRepository).all():
                for fname in fnames:
                    assert not os.path.isfile(os.path.join(ctx._archive_root, repo.name, fname))

            # ensure all source packages are deleted
            assert session.query(SourcePackage).count() == 0

    def test_sections_available(self, ctx):
        with session_scope() as session:
            sections = session.query(ArchiveSection).order_by(ArchiveSection.name).all()
            assert len(sections) == 59
            assert sections[0].name == 'admin'
            assert sections[-1].name == 'zope'

    def test_lintian(self, ctx, package_samples):
        assert shutil.which('bwrap') and shutil.which('lintian')

        lintian_conf = LintianConfig()
        fatal_tags = lintian_conf.fatal_tags.copy()
        assert len(fatal_tags) > 10

        bad_upload_fname = os.path.join(package_samples, 'linux_42.0-1_%s.changes' % ctx._host_arch)
        lint_success, lintian_tags = lintian_check(bad_upload_fname, tags=['no-copyright-file'])
        assert lintian_tags == [
            {'level': 'E', 'package': 'linux-image-all', 'tag': 'no-copyright-file', 'description': ''},
            {'level': 'E', 'package': 'linux-image-all-signed-template', 'tag': 'no-copyright-file', 'description': ''},
        ]
        assert not lint_success

        # try package with a larger filter
        bad_upload_fname = os.path.join(package_samples, 'pkg-all1_0.1-2_all.deb')
        lint_success, lintian_tags = lintian_check(bad_upload_fname, tags=fatal_tags)
        assert lintian_tags == [{'level': 'E', 'package': 'pkg-all1', 'tag': 'no-copyright-file', 'description': ''}]
        assert not lint_success

        # make check test succeed by allowing the offending issues
        fatal_tags.remove('no-copyright-file')
        lint_success, lintian_tags = lintian_check(bad_upload_fname, tags=fatal_tags)
        assert lintian_tags == []
        assert lint_success

        # try changes file with a larger filter
        bad_upload_fname = os.path.join(package_samples, 'package_0.2-1_%s.changes' % ctx._host_arch)
        lint_success, lintian_tags = lintian_check(bad_upload_fname, tags=fatal_tags)
        assert lintian_tags == [
            {
                'level': 'E',
                'package': 'package source',
                'tag': 'required-field',
                'description': '(in section for source) Standards-Version [debian/control:1]',
            },
            {
                'level': 'E',
                'package': 'package source',
                'tag': 'required-field',
                'description': 'package_0.2-1.dsc Standards-Version',
            },
        ]
        assert not lint_success

    def test_package_uploads(self, ctx, package_samples):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, 'master', 'unstable')

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
                os.path.join(ctx._archive_root, 'master', 'pool', 'main', 'p', 'package', 'package_0.1-1.dsc')
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
                os.path.join(ctx._archive_root, 'master', 'pool', 'main', 'p', 'package', 'package_0.1-1_all.deb')
            )

            # try importing a binary that does not have overrides set
            with pytest.raises(ArchiveImportError) as einfo:
                pi.import_binary(os.path.join(package_samples, 'snowman_0.1-1_all.deb'), 'main')
            assert 'Could not find corresponding source package' in str(einfo.value)
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
                os.path.join(ctx._archive_root, 'master', 'pool', 's', 'snowman', 'snowman_0.1-1_all.deb')
            )

            # add source package to NEW
            pi.import_source(os.path.join(package_samples, 'snowman_0.1-1.dsc'), 'main')
            session.commit()
            assert os.path.isfile(
                os.path.join(ctx._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')
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
                os.path.join(ctx._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1_all.deb')
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
                os.path.join(ctx._queue_root, 'master', 'new', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')
            )
            assert os.path.join(ctx._archive_root, 'master', 'pool', 'main', 's', 'snowman', 'snowman_0.1-1.dsc')

            # test processing an actual upload from a changes file
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            uh = UploadHandler(session, repo)
            uh.keep_source_packages = True

            # fail on a Lintian check
            uh.skip_lintian_check = False
            res = uh.process_changes(os.path.join(package_samples, 'package_0.2-1_%s.changes' % ctx._host_arch))
            assert 'Lintian issues were found' in res.error
            assert not res.success

            # actually accept the package (by skipping the Lintian check)
            uh.skip_lintian_check = True
            res = uh.process_changes(os.path.join(package_samples, 'package_0.2-1_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
            assert res.uploader.email == 'snowman@example.com'
            assert res.uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']

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
            res = uh.process_changes(os.path.join(package_samples, 'package_0.2-1_%s.changes' % ctx._host_arch))
            assert res.error == (
                'Your upload contains version "0.2-1" of source package "package", '
                'however we have already seen higher or equal version "0.2-1" in master:unstable before.\n'
                'Uploads must have a higher version than already present in the archive.'
            )
            assert not res.success
            assert res.uploader.email == 'snowman@example.com'
            assert res.uploader.pgp_fingerprints == ['589E8FA542378066E944B6222F7C63E8F3A2C549']

            # try importing a non-free package, this thing should end up in NEW
            res = uh.process_changes(os.path.join(package_samples, 'nonfree-package_0.1-1_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
            assert res.uploader.email == 'maint@example.com'
            assert res.uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']

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
            assert os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', nonfreepkg_pool_subdir))

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
                    ctx._queue_root,
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
            assert not os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', nonfreepkg_pool_subdir))
            assert os.path.join(ctx._archive_root, 'master', nonfreepkg_pool_subdir)

            # restore previously moved orig file that may exist from a failed run
            # if we are not regenerating the sample directory
            pkgnew_orig_fname = os.path.join(package_samples, 'pkgnew_0.1.orig.tar.gz')
            pkgnew_orig_moved_fname = os.path.join(package_samples, '_moved-pkgnew_0.1.orig.tar.gz')
            if os.path.isfile(pkgnew_orig_moved_fname):
                os.rename(pkgnew_orig_moved_fname, pkgnew_orig_fname)

            # process another upload, and reject it
            res = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-1_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
            assert res.uploader.email == 'maint@example.com'
            assert res.uploader.pgp_fingerprints == ['993C2870F54D83789E55323C13D986C3912E851C']
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

            pkg_pool_subdir = os.path.join('pool', 'main', 'p', 'pkgnew')
            pkg_pool_subloc = os.path.join(pkg_pool_subdir, 'pkgnew_0.1-1')
            assert os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', pkg_pool_subloc + '.dsc'))
            assert not os.path.isfile(os.path.join(ctx._archive_root, 'master', pkg_pool_subloc + '.dsc'))

            newqueue_reject(session, rss, spkg)
            assert not os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', pkg_pool_subloc + '.dsc'))
            assert not os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', pkg_pool_subloc + '.changes'))
            assert not os.path.isfile(os.path.join(ctx._archive_root, 'master', pkg_pool_subloc + '.dsc'))
            assert not os.path.isfile(os.path.join(pkg_pool_subdir, 'pkg-all1_0.1-1_all.deb'))
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
            res = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-1_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
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
            res = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-2_source.changes'))
            assert res.error is None
            assert res.success
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.name == 'pkgnew', SourcePackage.version == '0.1-2')
                .one()
            )
            missing_overrides = check_overrides_source(session, rss, spkg)
            # this package has 4 new binary packages
            assert len(missing_overrides) == 4
            assert os.path.isfile(os.path.join(ctx._queue_root, 'master', 'new', pkg_pool_subdir, 'pkgnew_0.1-2.dsc'))
            newqueue_accept(session, rss, spkg, missing_overrides)
            assert not os.path.isfile(
                os.path.join(ctx._queue_root, 'master', 'new', pkg_pool_subdir, 'pkgnew_0.1-2.dsc')
            )

            # add the missing binaries
            res = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-2_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'pkg-any1',
                    BinaryPackage.version == '0.1-2',
                    BinaryPackage.component.has(name='main'),
                    BinaryPackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert bpkg

            # pkgnew 0.1-3
            # we try to import this wothout imferring the orig.tar file from the upload directory, so we need
            # to move it out of the way temporarily
            os.rename(pkgnew_orig_fname, pkgnew_orig_moved_fname)
            res = uh.process_changes(os.path.join(package_samples, 'pkgnew_0.1-3_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
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
                    BinaryPackage.suites.any(ArchiveSuite.name == rss.suite.name),
                )
                .one_or_none()
            )
            assert bpkg
            # verify the orig files from the previous package have been registered with this one
            has_orig_tar = False
            has_dsc = False
            for file in spkg.files:
                if file.fname.endswith('dsc'):
                    has_dsc = True
                elif re_file_orig.match(os.path.basename(file.fname)):
                    has_orig_tar = True
            assert has_dsc
            assert has_orig_tar

            # move orig tarball back
            os.rename(pkgnew_orig_moved_fname, pkgnew_orig_fname)

        # the NEW queue should be completely empty now, for all suites and repos
        queue_entries_count = session.query(ArchiveQueueNewEntry).count()
        assert queue_entries_count == 0

    def test_package_delete(self, ctx, package_samples):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, 'master', 'unstable')

            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            uh = UploadHandler(session, repo)
            uh.keep_source_packages = True
            uh.skip_lintian_check = True

            # add package and verify that is exists in the archive
            res = uh.process_changes(os.path.join(package_samples, 'grave_0.1-1_%s.changes' % ctx._host_arch))
            assert res.error is None
            assert res.success
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
            assert os.path.isfile(os.path.join(ctx._archive_root, 'master', spkg.directory, 'grave_0.1-1.dsc'))
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
            assert os.path.isfile(os.path.join(ctx._archive_root, 'master', spkg.directory, 'grave_0.1-1_all.deb'))

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
            assert not os.path.isdir(os.path.join(ctx._archive_root, 'master', spkg_directory))

    def test_package_dbgsym_upload(self, ctx, package_samples):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, 'master', 'unstable')
            rss_dbg = repo_suite_settings_for_debug(session, rss)
            assert rss_dbg
            assert rss_dbg.repo.name == 'master-debug'
            assert rss_dbg.suite.name == 'unstable-debug'

            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            uh = UploadHandler(session, repo)
            uh.keep_source_packages = True
            uh.skip_lintian_check = True

            # add package and verify that is exists in the archive
            res = uh.process_changes(
                os.path.join(package_samples, 'main-contrib-with-debug_0.1-1_%s.changes' % ctx._host_arch)
            )
            assert res.error is None
            assert res.success
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'main-contrib-with-debug',
                    SourcePackage.version == '0.1-1',
                )
                .one_or_none()
            )
            assert spkg
            missing_overrides = check_overrides_source(session, rss, spkg)
            assert len(missing_overrides) == 2
            assert spkg.suites == []
            newqueue_accept(session, rss, spkg, missing_overrides, include_binaries=True)
            assert spkg.suites[0].name == 'unstable'
            assert spkg.component.name == 'main'
            assert os.path.isfile(
                os.path.join(ctx._archive_root, 'master', spkg.directory, 'main-contrib-with-debug_0.1-1.dsc')
            )

            # check where the debug package ended up
            session.commit()
            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss_dbg.repo_id,
                    BinaryPackage.name == 'contrib-with-debug-dbgsym',
                    BinaryPackage.version == '0.1-1',
                    BinaryPackage.component.has(name='contrib'),
                    BinaryPackage.suites.any(ArchiveSuite.name == rss_dbg.suite.name),
                )
                .one_or_none()
            )
            assert bpkg
            assert os.path.isfile(
                os.path.join(
                    ctx._archive_root,
                    'master-debug',
                    bpkg.directory,
                    'contrib-with-debug-dbgsym_0.1-1_%s.deb' % ctx._host_arch,
                )
            )

    def test_package_expire(self, ctx):
        with session_scope() as session:
            repo_suites = session.query(ArchiveRepoSuiteSettings).all()

            def fetch_deleted_pkg_info():
                deleted_pkgs_src = (
                    session.query(SourcePackage.name, SourcePackage.version)
                    .filter(~SourcePackage.time_deleted.is_(None))
                    .order_by(SourcePackage.name, SourcePackage.version)
                    .all()
                )
                deleted_pkgs_bin = (
                    session.query(BinaryPackage.name, BinaryPackage.version)
                    .filter(~BinaryPackage.time_deleted.is_(None))
                    .order_by(BinaryPackage.name, BinaryPackage.version)
                    .all()
                )
                return deleted_pkgs_src, deleted_pkgs_bin

            def fetch_pkg_suiteinfo():
                pkgs_src_suiteinfo = (
                    session.query(SourcePackage.name, SourcePackage.version, ArchiveSuite.name)
                    .join(SourcePackage.suites)
                    .order_by(SourcePackage.name, SourcePackage.version)
                    .all()
                )
                pkgs_bin_suiteinfo = (
                    session.query(BinaryPackage.name, BinaryPackage.version, ArchiveSuite.name)
                    .join(BinaryPackage.suites)
                    .order_by(BinaryPackage.name, BinaryPackage.version)
                    .all()
                )
                return pkgs_src_suiteinfo, pkgs_bin_suiteinfo

            # check that there are no packages marked for deletion
            deleted_pkgs_src, deleted_pkgs_bin = fetch_deleted_pkg_info()
            assert deleted_pkgs_src == []
            assert deleted_pkgs_bin == []
            pkgs_src_suiteinfo, pkgs_bin_suiteinfo = fetch_pkg_suiteinfo()
            assert pkgs_src_suiteinfo == [
                ('main-contrib-with-debug', '0.1-1', 'unstable'),
                ('nonfree-package', '0.1-1', 'unstable'),
                ('package', '0.1-1', 'unstable'),
                ('package', '0.2-1', 'unstable'),
                ('pkgnew', '0.1-1', 'unstable'),
                ('pkgnew', '0.1-2', 'unstable'),
                ('pkgnew', '0.1-3', 'unstable'),
                ('snowman', '0.1-1', 'unstable'),
            ]
            assert pkgs_bin_suiteinfo == [
                ('contrib-with-debug', '0.1-1', 'unstable'),
                ('contrib-with-debug-dbgsym', '0.1-1', 'unstable-debug'),
                ('main-package', '0.1-1', 'unstable'),
                ('package', '0.1-1', 'unstable'),
                ('package', '0.2-1', 'unstable'),
                ('pkg-all1', '0.1-3', 'unstable'),
                ('pkg-all2', '0.1-3', 'unstable'),
                ('pkg-all3', '0.1-3', 'unstable'),
                ('pkg-any1', '0.1-2', 'unstable'),
                ('pkg-any1', '0.1-3', 'unstable'),
                ('pkg-any2', '0.1-2', 'unstable'),
                ('pkg-any2', '0.1-3', 'unstable'),
                ('pkg-any3', '0.1-2', 'unstable'),
                ('pkg-any3', '0.1-3', 'unstable'),
                ('pkg-any4', '0.1-2', 'unstable'),
            ]

            # expire packages!
            for rss in repo_suites:
                expire_superseded(session, rss)

            # superseded versions should now be marked for removal
            deleted_pkgs_src, deleted_pkgs_bin = fetch_deleted_pkg_info()
            assert deleted_pkgs_src == [('package', '0.1-1'), ('pkgnew', '0.1-1'), ('pkgnew', '0.1-2')]
            assert deleted_pkgs_bin == [
                ('package', '0.1-1'),
                ('pkg-any1', '0.1-2'),
                ('pkg-any2', '0.1-2'),
                ('pkg-any3', '0.1-2'),
                ('pkg-any4', '0.1-2'),
            ]
            pkgs_src_suiteinfo, pkgs_bin_suiteinfo = fetch_pkg_suiteinfo()
            assert pkgs_src_suiteinfo == [
                ('main-contrib-with-debug', '0.1-1', 'unstable'),
                ('nonfree-package', '0.1-1', 'unstable'),
                ('package', '0.2-1', 'unstable'),
                ('pkgnew', '0.1-3', 'unstable'),
                ('snowman', '0.1-1', 'unstable'),
            ]
            assert pkgs_bin_suiteinfo == [
                ('contrib-with-debug', '0.1-1', 'unstable'),
                ('contrib-with-debug-dbgsym', '0.1-1', 'unstable-debug'),
                ('main-package', '0.1-1', 'unstable'),
                ('package', '0.2-1', 'unstable'),
                ('pkg-all1', '0.1-3', 'unstable'),
                ('pkg-all2', '0.1-3', 'unstable'),
                ('pkg-all3', '0.1-3', 'unstable'),
                ('pkg-any1', '0.1-3', 'unstable'),
                ('pkg-any2', '0.1-3', 'unstable'),
                ('pkg-any3', '0.1-3', 'unstable'),
            ]

    def test_heidi_import(self, ctx, samples_dir):
        # test import of Britney's Heidi report

        heidi_report_fname = os.path.join(samples_dir, 'spears', 'heidi-current')
        import_heidi_result.callback(suite_name='stable', heidi_fname=heidi_report_fname, allow_delete=True)

        with session_scope() as session:
            rss = repo_suite_settings_for(session, 'master', 'stable')

            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.name == 'pkgnew',
                    SourcePackage.version == '0.1-3',
                    SourcePackage.suites.any(ArchiveSuite.id == rss.suite_id),
                )
                .one_or_none()
            )
            assert spkg

            bpkg = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.name == 'pkg-all3',
                    BinaryPackage.version == '0.1-3',
                    BinaryPackage.component.has(name='main'),
                    BinaryPackage.suites.any(ArchiveSuite.id == rss.suite_id),
                )
                .one_or_none()
            )
            assert bpkg

    def test_publish(self, ctx, samples_dir):
        from lkarchive.publish import publish_repo_dists

        # link the DEP-11 fetch hook to its destination
        os.makedirs(ctx._lconf.data_import_hooks_dir, exist_ok=True)
        os.symlink(
            os.path.join(samples_dir, 'dep11', 'fetch-appstream.sh'),
            os.path.join(ctx._lconf.data_import_hooks_dir, 'fetch-appstream.sh'),
        )

        # publish the "master" repository data
        with session_scope() as session:
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
            publish_repo_dists(session, repo)

            # check if key files are there
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/Release'))
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/Release.gpg'))
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/InRelease'))
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/main/binary-all/Packages.xz'))
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/main/source/Sources.xz'))
            assert os.path.isfile(
                os.path.join(repo.get_root_dir(), 'dists/unstable/main/dep11/Components-amd64.yml.xz')
            )
            assert os.path.isfile(os.path.join(repo.get_root_dir(), 'dists/unstable/main/dep11/icons-64x64.tar.gz'))

            # check if software components are present
            assert session.query(SoftwareComponent).count() == 3
            sw = session.query(SoftwareComponent).filter(SoftwareComponent.cid == 'org.freedesktop.appstream.cli').one()
            assert len(sw.pkgs_binary) == 1
            assert sw.pkgs_binary[0].name == 'pkg-any3'
