# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import pytest

import laniakea.typing as T
from laniakea.db import (
    DebType,
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    PackagePriority,
    ArchiveComponent,
    ArchiveArchitecture,
)
from laniakea.utils.gpg import GpgException
from laniakea.reporeader import RepositoryReader


def validate_src_packages(spkgs: T.List[SourcePackage]):
    assert len(spkgs) == 8

    found = False
    for spkg in spkgs:
        if spkg.name != '0ad':
            continue
        found = True

        assert spkg.version == '0.0.20-1'
        assert spkg.maintainer == 'Debian Games Team <pkg-games-devel@lists.alioth.debian.org>'
        assert spkg.uploaders == ['Vincent Cheng <vcheng@debian.org>']

        assert spkg.build_depends == [
            'autoconf',
            'debhelper (>= 9)',
            'dpkg-dev (>= 1.15.5)',
            'libboost-dev',
            'libboost-filesystem-dev',
            'libcurl4-gnutls-dev | libcurl4-dev',
            'libenet-dev (>= 1.3)',
            'libgloox-dev (>= 1.0.9)',
            'libicu-dev',
            'libminiupnpc-dev (>= 1.6)',
            'libnspr4-dev',
            'libnvtt-dev (>= 2.0.8-1+dfsg-4~)',
            'libogg-dev',
            'libopenal-dev',
            'libpng-dev',
            'libsdl2-dev (>= 2.0.2)',
            'libvorbis-dev',
            'libwxgtk3.0-dev | libwxgtk2.8-dev',
            'libxcursor-dev',
            'libxml2-dev',
            'pkg-config',
            'zlib1g-dev',
        ]

        assert spkg.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
        assert spkg.standards_version == '3.9.7'
        assert spkg.format_version == '3.0 (quilt)'

        assert spkg.homepage == 'http://play0ad.com/'
        assert spkg.vcs_browser == 'https://anonscm.debian.org/viewvc/pkg-games/packages/trunk/0ad/'
        assert spkg.directory == 'pool/main/0/0ad'

        assert len(spkg.files) == 3
        for f in spkg.files:
            if f.fname.endswith('.dsc'):
                assert f.fname == 'pool/main/0/0ad/0ad_0.0.20-1.dsc'
                assert f.size == 2455
                assert f.sha256sum == 'f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955'
            elif f.fname.endswith('.debian.tar.xz'):
                assert f.fname == 'pool/main/0/0ad/0ad_0.0.20-1.debian.tar.xz'
                assert f.size == 70688
                assert f.sha256sum == '3256f0a33654aa8c22605c693be3dd3a11b4fdb7c7e2a9016670f28f135d1737'
            elif f.fname.endswith('.orig.tar.xz'):
                assert f.fname == 'pool/main/0/0ad/0ad_0.0.20.orig.tar.xz'
                assert f.size == 25610932
                assert f.sha256sum == 'a396d5cb37057ddd3cd523434f70c56be21588a2228443e7508d2b2d610fc68e'
            else:
                print('Bad file: {}'.format(f))
                assert 0

        assert len(spkg.expected_binaries) == 2
        for b in spkg.expected_binaries:
            if b.name == '0ad':
                assert b.deb_type == DebType.DEB
                assert b.version == spkg.version
                assert b.section == 'games'
                assert b.priority == PackagePriority.OPTIONAL
                assert b.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
            elif b.name == '0ad-dbg':
                assert b.deb_type == DebType.DEB
                assert b.version == spkg.version
                assert b.section == 'debug'
                assert b.priority == PackagePriority.EXTRA
                assert b.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
            else:
                print('Bad binary package: {}'.format(b))
                assert 0
    assert found


def validate_bin_packages(bpkgs: T.List[BinaryPackage]):
    assert len(bpkgs) == 7

    found = False
    for pkg in bpkgs:
        if pkg.name != 'kernel-wedge':
            continue
        found = True

        assert pkg.version == '2.94'
        assert pkg.maintainer == 'Debian Install System Team <debian-boot@lists.debian.org>'

        assert pkg.depends == ['debhelper (>= 9)', 'make']

        assert pkg.architecture.name == 'all'
        assert pkg.override.section == 'utils'
        assert pkg.override.priority == PackagePriority.OPTIONAL
        assert pkg.size_installed == 89

        assert pkg.bin_file.fname == 'pool/main/k/kernel-wedge/kernel-wedge_2.94_all.deb'
        assert pkg.bin_file.size == 39766
        assert pkg.bin_file.sha256sum == 'c0915bf4c3d6d42525c93827d9fd107447d68942e4a187fcbf4c68e78a12a6cf'
    assert found


def test_reporeader_local(samples_dir, localconfig):
    keyrings = localconfig.trusted_gpg_keyrings
    repo_location = os.path.join(samples_dir, 'samplerepo', 'dummy')

    suite = ArchiveSuite('testing')
    component = ArchiveComponent('main')
    arch = ArchiveArchitecture('amd64')
    arch_all = ArchiveArchitecture('all')
    repo_reader = RepositoryReader(repo_location, 'Dummy', trusted_keyrings=[])

    # we have no keyrings set, so this should fail
    with pytest.raises(GpgException):
        src_pkgs = repo_reader.source_packages(suite, component)

    # try again!
    repo_reader = RepositoryReader(repo_location, 'Dummy', trusted_keyrings=keyrings)
    src_pkgs = repo_reader.source_packages(suite, component)
    bin_pkgs = repo_reader.binary_packages(suite, component, arch)
    assert len(bin_pkgs) == 4
    bin_pkgs.extend(repo_reader.binary_packages(suite, component, arch_all))

    # check packages
    assert len(src_pkgs) == 8
    assert len(bin_pkgs) == 7

    validate_src_packages(src_pkgs)
    validate_bin_packages(bin_pkgs)
