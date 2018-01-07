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
import std.string : strip, format, endsWith, indexOf;
import std.array : appender, split, empty;
import std.conv : to;
import std.typecons : Flag, Yes, No;
import std.digest.sha;
import std.algorithm : canFind;
static import std.file;

import laniakea.logging;
import laniakea.net : downloadFile;
import laniakea.localconfig : LocalConfig;
import laniakea.utils : isRemote, splitStrip, compareVersions, hashFile;
import laniakea.tagfile;
import laniakea.pkgitems;

import laniakea.db.schema.core : ArchiveArchitecture;


/**
 * Allows reading data from a Debian repository.
 */
class Repository
{

private:

    struct InReleaseData
    {
        ArchiveFile[] files;
    }

    string rootDir;
    string repoUrl;
    string repoName;
    string[] keyrings;
    bool repoTrusted;

    InReleaseData[string] inRelease;

public:

    @trusted
    this (string location, string repoName = null, string[] trustedKeyrings = [])
    {
        if (isRemote (location)) {
            auto conf = LocalConfig.get;
            rootDir = buildPath (conf.cacheDir, "repos_tmp", repoName);
            std.file.mkdirRecurse (rootDir);
            repoUrl = location;
        } else {
            rootDir = location;
            repoUrl = null;
        }

        keyrings = trustedKeyrings;
        repoTrusted = false;
        this.repoName = repoName;
    }

    @property @safe
    string baseDir () { return rootDir; }

    void setTrusted (bool trusted)
    {
        repoTrusted = trusted;
        logDebug ("Marked repository '%s' as trusted.", repoLocation);
    }

    @property @safe
    private string repoLocation ()
    {
        if (repoUrl.empty)
            return rootDir;
        return repoUrl;
    }

    /**
     * Download a file and retrieve a filename.
     *
     * This function does not validate the result, this step
     * has to be done by the caller.
     */
    private string getRepoFileInternal (const string location) @trusted
    {
        if (repoUrl is null) {
            immutable fname = buildPath (rootDir, location);
            if (std.file.exists (fname))
                return fname;
        } else {
            immutable sourceUrl = buildPath (repoUrl, location);
            immutable targetFname = buildPath (rootDir, location);
            std.file.mkdirRecurse (targetFname.dirName);

            downloadFile (sourceUrl, targetFname);
            return targetFname;
        }

        // There was an error, we couldn't find or download the file
        logError ("Could not find repository file '%s'", location);
        return null;
    }

    private InReleaseData getRepoInformation (string suite)
    {
        import laniakea.utils.gpg : SignedFile;

        auto irP = suite in inRelease;
        if (irP !is null)
            return *irP;

        auto tf = new TagFile;
        immutable irfname = getRepoFileInternal (buildPath ("dists", suite, "InRelease"));
        if (irfname.empty)
            return InReleaseData ();

        if (keyrings.empty) {
            // TODO: Maybe make this error fatal? Or should we allow this behavior for convenience?
            if (!repoTrusted)
                logError ("Can not validate repository '%s': No trusted keys found.", repoLocation);
            tf.open (irfname);
        } else {
            auto sf = new SignedFile (keyrings);
            sf.open (irfname);
            tf.load (sf.content);
        }

        auto ird = InReleaseData ();

        auto filesRaw = tf.readField ("SHA256");
        ird.files = parseChecksumsList (filesRaw);

        inRelease[suite] = ird;
        return ird;
    }

    /**
     * Retrieve a package list (index) file from the repository.
     * The file will be downloaded if necessary:
     *
     * Returns: A file path to the index file.
     */
    public string getIndexFile (string suite, string fname)
    {
        auto ird = getRepoInformation (suite);
        immutable indexFname = getRepoFileInternal (buildPath ("dists", suite, fname));
        if (indexFname.empty)
            return null;

        // if we can not validate, just continue
        if (keyrings.empty)
            return indexFname;

        // validate the file
        immutable hash = hashFile!SHA256 (indexFname);
        bool valid = false;
        foreach (ref file; ird.files) {
            if (file.fname == fname) {
                if (hash != file.sha256sum)
                    throw new Exception ("Checksum validation of '%s' failed (%s != %s).".format (fname, hash, file.sha256sum));
                valid = true;
            }
        }

        if (!valid)
            throw new Exception ("Unable to validate '%s': File not mentioned in InRelease.".format (fname));

        return indexFname;
    }

    /**
     * Return a list of all source packages in the given suite and component.
     */
    SourcePackage[] getSourcePackages (const string suite, const string component)
    {
        immutable indexFname = getIndexFile (suite, buildPath (component, "source", "Sources.xz"));
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
            pkg.suite = suite;
            pkg.component = component;
            pkg.repository = repoName;

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

            pkg.files = parseChecksumsList (tf.readField ("Checksums-Sha256"), pkg.directory);

            immutable rawPkgList = tf.readField ("Package-List");
            if (rawPkgList is null) {
                foreach (bin; tf.readField ("Binary", "").splitStrip (",")) {
                    PackageInfo pi;
                    pi.debType = DebType.DEB;
                    pi.name = bin;
                    pi.ver = pkg.ver;
                    pkg.binaries ~= pi;
                }
            } else {
                pkg.binaries = parsePackageListString (rawPkgList, pkg.ver);
            }

            // Do some issue-reporting
            if (pkg.files.empty)
                logWarning ("Source package %s/%s seems to have no files (in %s).", pkg.name, pkg.ver, repoLocation);

            pkgs ~= pkg;
        } while (tf.nextSection ());

        return pkgs.data;
    }

    /**
     * Internal
     */
    @safe
    private BinaryPackage[] readBinaryPackagesFromData (TagFile tf, string suiteName, string component)
    {
        auto pkgs = appender!(BinaryPackage[]);
        do {
            auto pkgname = tf.readField ("Package");
            if (!pkgname)
                continue;

            BinaryPackage pkg;
            pkg.name = pkgname;
            pkg.suite = suiteName;
            pkg.component = component;
            pkg.repository = repoName;

            pkg.ver = tf.readField ("Version");
            pkg.architecture = new ArchiveArchitecture (tf.readField ("Architecture"));
            pkg.maintainer = tf.readField ("Maintainer");

            immutable sourceId = tf.readField ("Source");
            if (sourceId is null) {
                pkg.sourceName = pkg.name;
                pkg.sourceVersion = pkg.ver;
            } else if (sourceId.canFind ("(")) {
                pkg.sourceName = sourceId[0..sourceId.indexOf ("(")-1].strip;
                pkg.sourceVersion = sourceId[sourceId.indexOf ("(")+1..sourceId.indexOf (")")].strip;
            } else {
                pkg.sourceName = sourceId;
                pkg.sourceVersion = pkg.ver;
            }

            immutable isize = tf.readField ("Installed-Size");
            if (!isize.empty)
                pkg.installedSize = to!int (tf.readField ("Installed-Size"));

            pkg.depends = tf.readField ("Depends", "").splitStrip (",");
            pkg.preDepends = tf.readField ("Pre-Depends", "").splitStrip (",");

            pkg.homepage = tf.readField ("Homepage");
            pkg.section = tf.readField ("Section");

            pkg.description = tf.readField ("Description");
            pkg.descriptionMd5 = tf.readField ("Description-md5");

            pkg.priority = packagePriorityFromString (tf.readField ("Priority"));

            pkg.file.fname = tf.readField ("Filename");

            immutable size = tf.readField ("Size");
            if (!size.empty)
                pkg.file.size = to!size_t (tf.readField ("Size"));
            pkg.file.sha256sum = tf.readField ("SHA256");

            pkg.debType = DebType.DEB;
            if (pkg.file.fname.endsWith (".udeb"))
                pkg.debType = DebType.UDEB;

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
        immutable indexFname = getIndexFile (suite, buildPath (component, "binary-%s".format (arch), "Packages.xz"));
        if (indexFname.empty)
            return [];

        auto tf = new TagFile;
        tf.open (indexFname);

        return readBinaryPackagesFromData (tf, suite, component);
    }

    /**
     * Get a list of binary installer packages for the given repository suite, component
     * and architecture.
     * These binary packages are typically udebs used by the debian-installer, and should not
     * be installed on an user's system.
     */
    BinaryPackage[] getInstallerPackages (const string suite, const string component, const string arch)
    {
        immutable indexFname = getIndexFile (suite, buildPath (component, "debian-installer", "binary-%s".format (arch), "Packages.xz"));
        if (indexFname.empty)
            return [];

        auto tf = new TagFile;
        tf.open (indexFname);

        return readBinaryPackagesFromData (tf, suite, component);
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
        auto epkgP = pkg.name in res;
        if (epkgP is null) {
            res[pkg.name] = pkg;
        } else {
            auto epkg = *epkgP;
            if (compareVersions (pkg.ver, epkg.ver) > 0) {
                res[pkg.name] = pkg;
            }
        }
    }

    return res;
}
