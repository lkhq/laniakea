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

module laniakea.repository.repository;
@safe:

import std.stdio;
import std.path : buildPath, dirName;
import std.string : strip, format, endsWith;
import std.array : appender, split, empty;
import std.conv : to;
import std.typecons : Flag, Yes, No;
import std.digest.sha;
static import std.file;

import requests : getContent;

import laniakea.logging;
import laniakea.config : BaseConfig;
import laniakea.utils : isRemote, splitStrip, compareVersions, hashFile;
import laniakea.tagfile;
import laniakea.pkgitems;


/**
 * Allows reading data from a Debian repository.
 */
class Repository
{

private:
    string rootDir;
    string repoUrl;

public:

    @trusted
    this (string location, string repoName = null)
    {
        if (isRemote (location)) {
            auto conf = BaseConfig.get ();
            rootDir = buildPath (conf.cacheDir, "repos_tmp", repoName);
            std.file.mkdirRecurse (rootDir);
            repoUrl = location;
        } else {
            rootDir = location;
            repoUrl = null;
        }
    }

    /**
     * Download a file and retrieve a filename.
     *
     * This function does not validate the result, this step
     * has to be done by the caller.
     */
    private string getRepoFileInternal (const string repoLocation) @trusted
    {
        if (repoUrl is null) {
            immutable fname = buildPath (rootDir, repoLocation);
            if (std.file.exists (fname))
                return fname;
        } else {
            immutable sourceUrl = buildPath (repoUrl, repoLocation);
            immutable targetFname = buildPath (rootDir, repoLocation);
            std.file.mkdirRecurse (targetFname.dirName);

            auto content = getContent (sourceUrl);
            auto f = File (targetFname, "wb");
            f.rawWrite (content.data);
            f.close ();

            return targetFname;
        }

        // There was an error, we couldn't find or download the file
        logError ("Could not find repository file '%s'", repoLocation);
        return null;
    }

    @property @safe
    string baseDir () { return rootDir; }

    /**
     * Return a list of all source packages in the given suite and component.
     */
    SourcePackage[] getSourcePackages (const string suite, const string component)
    {
        immutable indexFname = getRepoFileInternal (buildPath ("dists", suite, component, "source", "Sources.xz"));
        if (indexFname.empty)
            return [];

        auto tf = new TagFile;
        tf.open (indexFname);

        auto pkgs = appender!(SourcePackage[]);
        do {
            auto pkgname = tf.readField ("Package");
            if (!pkgname)
                continue;

            SourcePackage pkg;
            pkg.name = pkgname;

            pkg.ver = tf.readField ("Version");
            pkg.architectures = tf.readField ("Architecture").split (" ");
            pkg.standardsVersion = tf.readField ("Standards-Version");
            pkg.format = tf.readField ("Format");

            pkg.vcsBrowser = tf.readField ("Vcs-Browser");
            pkg.homepage = tf.readField ("Homepage");
            pkg.maintainer = tf.readField ("Maintainer");
            pkg.uploaders = tf.readField ("Uploaders", "").splitStrip (","); // FIXME: Careful! Splitting just by comma isn't enough! We need to parse this properly.

            pkg.buildDepends = tf.readField ("Build-Depends", "").splitStrip (",");
            pkg.directory = tf.readField ("Directory");

            auto files = appender!(ArchiveFile[]);
            immutable filesRaw = tf.readField ("Checksums-Sha256"); // f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955 2455 0ad_0.0.20-1.dsc
            foreach (ref fileRaw; filesRaw.split ('\n')) {
                auto parts = fileRaw.strip.split (" ");
                if (parts.length != 3)
                    continue;

                ArchiveFile file;
                file.sha256sum = parts[0];
                file.size = to!size_t (parts[1]);
                file.fname = buildPath (pkg.directory, parts[2]);

                files ~= file;
            }
            pkg.files = files.data;

            immutable rawPkgList = tf.readField ("Package-List");
            if (rawPkgList is null) {
                foreach (bin; tf.readField ("Binary", "").splitStrip (",")) {
                    PackageInfo pi;
                    pi.type = DebType.DEB;
                    pi.name = bin;
                    pi.ver = pkg.ver;
                    pkg.binaries ~= pi;
                }
            } else {
                pkg.binaries = parsePackageListString (rawPkgList, pkg.ver);
            }

            // Do some issue-reporting
            if (pkg.files.empty)
                logWarning ("Source package %s/%s seems to have no files.", pkg.name, pkg.ver);

            pkgs ~= pkg;
        } while (tf.nextSection ());

        return pkgs.data;
    }

    /**
     * Internal
     */
    @safe
    private BinaryPackage[] readBinaryPackagesFromData (TagFile tf)
    {
        auto pkgs = appender!(BinaryPackage[]);
        do {
            auto pkgname = tf.readField ("Package");
            if (!pkgname)
                continue;

            BinaryPackage pkg;
            pkg.name = pkgname;

            pkg.ver = tf.readField ("Version");
            pkg.architecture = tf.readField ("Architecture");
            pkg.maintainer = tf.readField ("Maintainer");

            immutable isize = tf.readField ("Installed-Size");
            if (!isize.empty)
                pkg.installedSize = to!size_t (tf.readField ("Installed-Size"));

            pkg.depends = tf.readField ("Depends", "").splitStrip (",");
            pkg.preDepends = tf.readField ("Pre-Depends", "").splitStrip (",");

            pkg.homepage = tf.readField ("Homepage");
            pkg.section = tf.readField ("Section");

            pkg.priority = packagePriorityFromString (tf.readField ("Priority"));

            pkg.file.fname = tf.readField ("Filename");

            immutable size = tf.readField ("Size");
            if (!size.empty)
                pkg.file.size = to!size_t (tf.readField ("Size"));
            pkg.file.sha256sum = tf.readField ("SHA256");

            pkg.type = DebType.DEB;
            if (pkg.file.fname.endsWith (".udeb"))
                pkg.type = DebType.UDEB;

            // Do some issue-reporting
            if (pkg.file.fname.empty)
                logWarning ("Binary package %s/%s seems to have no files.", pkg.name, pkg.ver);

            pkgs ~= pkg;
        } while (tf.nextSection ());

        return pkgs.data;
    }

    /**
     * Get a list of binary package information for the given repository suite,
     * component and architecture.
     */
    BinaryPackage[] getBinaryPackages (const string suite, const string component, const string arch)
    {
        immutable indexFname = getRepoFileInternal (buildPath ("dists", suite, component, "binary-%s".format (arch), "Packages.xz"));
        if (indexFname.empty)
            return [];

        auto tf = new TagFile;
        tf.open (indexFname);

        return readBinaryPackagesFromData (tf);
    }

    /**
     * Get a list of binary installer packages for the given repository suite, component
     * and architecture.
     * These binary packages are typically udebs used by the debian-installer, and should not
     * be installed on an user's system.
     */
    BinaryPackage[] getInstallerPackages (const string suite, const string component, const string arch)
    {
        immutable indexFname = getRepoFileInternal (buildPath ("dists", suite, component, "debian-installer", "binary-%s".format (arch), "Packages.xz"));
        if (indexFname.empty)
            return [];

        auto tf = new TagFile;
        tf.open (indexFname);

        return readBinaryPackagesFromData (tf);
    }

    /**
     * Get a file from the repository.
     * Returns:
     *          An absolute path to the repository file.
     */
    string getFile (ArchiveFile afile, Flag!"validate" validate = Yes.validate)
    {
        immutable fname = getRepoFileInternal (afile.fname);

        if (validate) {
            immutable hash = hashFile!SHA256 (fname);
            if (hash != afile.sha256sum)
                throw new Exception ("Checksum validation of '%s' failed (%s != %s).".format (fname, hash, afile.sha256sum));
        }

        return fname;
    }

}

public T[string] getNewestPackagesMap(T) (T[] pkgList)
{
    T[string] res;

    foreach (ref pkg; pkgList) {
        if (pkg.name in res) {
            auto epkg = res[pkg.name];
            if (compareVersions (epkg.ver, pkg.ver) > 0)
                res[pkg.name] = pkg;
        } else {
            res[pkg.name] = pkg;
        }
    }

    return res;
}
