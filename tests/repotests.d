/*
 * Copyright (C) 2016 Matthias Klumpp <matthias@tenstral.net>
 *
 * Licensed under the GNU Lesser General Public License Version 3
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the license, or
 * (at your option) any later version.
 *
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this software.  If not, see <http://www.gnu.org/licenses/>.
 */

import std.stdio;
import std.path : buildPath;
import std.string : startsWith, endsWith;
import std.algorithm;

import testutils;
import laniakea.pkgitems;
import laniakea.repository;


void validateSourcePackages (SourcePackage[] srcPkgs)
{
    assertEq (srcPkgs.length, 6);

    bool found = false;
    foreach (ref spkg; srcPkgs) {
        if (spkg.name != "0ad")
            continue;
        found = true;

        assertEq (spkg.ver, "0.0.20-1");
        assertEq (spkg.maintainer, "Debian Games Team <pkg-games-devel@lists.alioth.debian.org>");
        assertEq (spkg.uploaders, ["Vincent Cheng <vcheng@debian.org>"]);

        assertEq (spkg.buildDepends, ["autoconf", "debhelper (>= 9)", "dpkg-dev (>= 1.15.5)", "libboost-dev",
                                "libboost-filesystem-dev", "libcurl4-gnutls-dev | libcurl4-dev", "libenet-dev (>= 1.3)",
                                "libgloox-dev (>= 1.0.9)", "libicu-dev", "libminiupnpc-dev (>= 1.6)", "libnspr4-dev",
                                "libnvtt-dev (>= 2.0.8-1+dfsg-4~)", "libogg-dev", "libopenal-dev", "libpng-dev",
                                "libsdl2-dev (>= 2.0.2)", "libvorbis-dev", "libwxgtk3.0-dev | libwxgtk2.8-dev",
                                "libxcursor-dev", "libxml2-dev", "pkg-config", "zlib1g-dev"]);

        assertEq (spkg.architectures, ["amd64", "arm64", "armhf", "i386", "kfreebsd-amd64", "kfreebsd-i386"]);
        assertEq (spkg.standardsVersion, "3.9.7");
        assertEq (spkg.format, "3.0 (quilt)");

        assertEq (spkg.homepage, "http://play0ad.com/");
        assertEq (spkg.vcsBrowser, "https://anonscm.debian.org/viewvc/pkg-games/packages/trunk/0ad/");
        assertEq (spkg.directory, "pool/main/0/0ad");

        //! assertEq (spkg.section, "misc");

        assertEq (spkg.files.length, 3);
        foreach (ref file; spkg.files) {
            if (file.fname.endsWith (".dsc")) {
                assertEq (file.fname, "pool/main/0/0ad/0ad_0.0.20-1.dsc");
                assertEq (file.size, 2455);
                assertEq (file.sha256sum, "f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955");
            } else if (file.fname.endsWith (".debian.tar.xz")) {
                assertEq (file.fname, "pool/main/0/0ad/0ad_0.0.20-1.debian.tar.xz");
                assertEq (file.size, 70688);
                assertEq (file.sha256sum, "3256f0a33654aa8c22605c693be3dd3a11b4fdb7c7e2a9016670f28f135d1737");
            } else if (file.fname.endsWith (".orig.tar.xz")) {
                assertEq (file.fname, "pool/main/0/0ad/0ad_0.0.20.orig.tar.xz");
                assertEq (file.size, 25610932);
                assertEq (file.sha256sum, "a396d5cb37057ddd3cd523434f70c56be21588a2228443e7508d2b2d610fc68e");
            } else {
                writeln ("Bad file: ", file);
                assert (0);
            }
        }

        assertEq (spkg.binaries.length, 2);
        foreach (ref bin; spkg.binaries) {
            if (bin.name == "0ad") {
                assertEq (bin.type, DebType.DEB);
                assertEq (bin.ver, spkg.ver);
                assertEq (bin.section, "games");
                assertEq (bin.priority, PackagePriority.OPTIONAL);
                assertEq (bin.architectures, ["amd64", "arm64", "armhf", "i386", "kfreebsd-amd64", "kfreebsd-i386"]);
            } else if (bin.name == "0ad-dbg") {
                assertEq (bin.type, DebType.DEB);
                assertEq (bin.ver, spkg.ver);
                assertEq (bin.section, "debug");
                assertEq (bin.priority, PackagePriority.EXTRA);
                assertEq (bin.architectures, ["amd64", "arm64", "armhf", "i386", "kfreebsd-amd64", "kfreebsd-i386"]);
            } else {
                writeln ("Bad binary package: ", bin);
                assert (0);
            }
        }

    }
    assert (found);
}

void validateBinaryPackages (BinaryPackage[] binPkgs)
{
    assertEq (binPkgs.length, 7);

    bool found = false;
    foreach (ref pkg; binPkgs) {
        if (pkg.name != "kernel-wedge")
            continue;
        found = true;

        assertEq (pkg.ver, "2.94");
        assertEq (pkg.maintainer, "Debian Install System Team <debian-boot@lists.debian.org>");

        assertEq (pkg.depends, ["debhelper (>= 9)", "make"]);

        assertEq (pkg.architecture, "all");
        assertEq (pkg.section, "utils");
        assertEq (pkg.priority, PackagePriority.OPTIONAL);
        assertEq (pkg.installedSize, 89);

        assertEq (pkg.file.fname, "pool/main/k/kernel-wedge/kernel-wedge_2.94_all.deb");
        assertEq (pkg.file.size, 39766);
        assertEq (pkg.file.sha256sum, "c0915bf4c3d6d42525c93827d9fd107447d68942e4a187fcbf4c68e78a12a6cf");
    }
    assert (found);
}

void testRepositoryRead (const string datadir)
{
    printTestInfo ("Repository (Read)");

    auto repo = new Repository (buildPath (datadir, "samplerepo", "dummy"), "dummy");

    auto srcPkgs = repo.getSourcePackages ("testing", "main");
    validateSourcePackages (srcPkgs);

    auto binPkgs = repo.getBinaryPackages ("testing", "main", "amd64");
    validateBinaryPackages (binPkgs);
}
