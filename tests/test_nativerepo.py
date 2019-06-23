# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
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
from laniakea.lknative import Repository
from laniakea.db import DebType, PackagePriority


def validate_src_packages(spkgs):
    assert len(spkgs) == 8

    found = False
    for spkg in spkgs:
        if spkg.name != '0ad':
            continue
        found = True

        assert spkg.ver, '0.0.20-1'
        assert spkg.maintainer == 'Debian Games Team <pkg-games-devel@lists.alioth.debian.org>'
        assert spkg.uploaders == ['Vincent Cheng <vcheng@debian.org>']

        assert spkg.buildDepends == ['autoconf', 'debhelper (>= 9)', 'dpkg-dev (>= 1.15.5)', 'libboost-dev',
                                     'libboost-filesystem-dev', 'libcurl4-gnutls-dev | libcurl4-dev', 'libenet-dev (>= 1.3)',
                                     'libgloox-dev (>= 1.0.9)', 'libicu-dev', 'libminiupnpc-dev (>= 1.6)', 'libnspr4-dev',
                                     'libnvtt-dev (>= 2.0.8-1+dfsg-4~)', 'libogg-dev', 'libopenal-dev', 'libpng-dev',
                                     'libsdl2-dev (>= 2.0.2)', 'libvorbis-dev', 'libwxgtk3.0-dev | libwxgtk2.8-dev',
                                     'libxcursor-dev', 'libxml2-dev', 'pkg-config', 'zlib1g-dev']

        assert spkg.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
        assert spkg.standardsVersion == '3.9.7'
        assert spkg.format == '3.0 (quilt)'

        assert spkg.homepage == 'http://play0ad.com/'
        assert spkg.vcsBrowser == 'https://anonscm.debian.org/viewvc/pkg-games/packages/trunk/0ad/'
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

        assert len(spkg.binaries) == 2
        for b in spkg.binaries:
            if b.name == '0ad':
                assert b.debType == DebType.DEB
                assert b.ver == spkg.ver
                assert b.section == 'games'
                assert b.priority == PackagePriority.OPTIONAL
                assert b.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
            elif b.name == '0ad-dbg':
                assert b.debType == DebType.DEB
                assert b.ver == spkg.ver
                assert b.section == 'debug'
                assert b.priority == PackagePriority.EXTRA
                assert b.architectures == ['amd64', 'arm64', 'armhf', 'i386', 'kfreebsd-amd64', 'kfreebsd-i386']
            else:
                print('Bad binary package: {}'.format(b))
                assert 0
    assert found


def validate_bin_packages(bpkgs):
    assert len(bpkgs) == 7

    found = False
    for pkg in bpkgs:
        if pkg.name != 'kernel-wedge':
            continue
        found = True

        assert pkg.ver == '2.94'
        assert pkg.maintainer == 'Debian Install System Team <debian-boot@lists.debian.org>'

        assert pkg.depends == ['debhelper (>= 9)', 'make']

        # FIXME: assert pkg.architecture.name == 'all'
        assert pkg.section == 'utils'
        assert pkg.priority == PackagePriority.OPTIONAL
        assert pkg.installedSize == 89

        assert pkg.file.fname == 'pool/main/k/kernel-wedge/kernel-wedge_2.94_all.deb'
        assert pkg.file.size == 39766
        assert pkg.file.sha256sum == 'c0915bf4c3d6d42525c93827d9fd107447d68942e4a187fcbf4c68e78a12a6cf'
    assert found


def test_repo_read(samplesdir, localconfig):
    repo = Repository(os.path.join(samplesdir, 'samplerepo', 'dummy'),
                      localconfig.cache_dir,
                      'dummy',
                      localconfig.trusted_gpg_keyrings)

    src_pkgs = repo.getSourcePackages('testing', 'main')
    validate_src_packages(src_pkgs)

    bin_pkgs = repo.getBinaryPackages('testing', 'main', 'amd64')
    bin_pkgs.extend(repo.getBinaryPackages('testing', 'main', 'all'))
    validate_bin_packages(bin_pkgs)
