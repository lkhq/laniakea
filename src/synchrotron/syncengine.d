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

import std.array : empty;
import std.string : endsWith;
import std.algorithm : canFind;
import std.array : appender;
import std.parallelism : parallel;

import laniakea.repository;
import laniakea.repository.dak;
import laniakea.pkgitems;
import laniakea.utils : compareVersions, getDebianRev;
import laniakea.config;
import laniakea.logging;

/**
 * Thrown on a package sync error.
 */
class PackageSyncError: Error
{
    @safe pure nothrow
    this (string msg, string file = __FILE__, size_t line = __LINE__, Throwable next = null)
    {
        super (msg, file, line, next);
    }
}

/**
 * Execute package synchronization in Synchrotron
 */
class SyncEngine
{

private:

    Dak dak;
    BaseConfig conf;
    bool m_importsTrusted;

    Repository sourceRepo;
    Repository targetRepo;

public:

    this ()
    {
        dak = new Dak ();
        conf = BaseConfig.get ();

        // the repository of the distribution we import stuff into
        targetRepo = new Repository (conf.archive.rootPath,
                                     conf.projectName);
        targetRepo.setTrusted (true);

        // the repository of the distribution we use to sync stuff from
        sourceRepo = new Repository (conf.synchrotron.sourceRepoUrl,
                                     conf.synchrotron.sourceName,
                                     conf.synchrotron.sourceKeyrings);
        m_importsTrusted = true; // we trust everything by default
    }

    @property
    bool importsTrusted ()
    {
        return m_importsTrusted;
    }

    @property
    void importsTrusted (bool v)
    {
        m_importsTrusted = v;
    }

    private void checkSyncReady ()
    {
        if (!conf.synchrotron.syncEnabled)
            throw new PackageSyncError ("Synchronization is disabled.");
    }

    /**
     * Get an associative array of the newest packages present in the repository
     * we should import packages from.
     */
    private T[string] getSourceRepoPackageMap(T) (string component, string arch = null)
        if (is(T == SourcePackage) || is(T == BinaryPackage))
    {
        T[] pkgList;
        static if (is(T == SourcePackage)) {
            pkgList = sourceRepo.getSourcePackages (conf.synchrotron.sourceSuite.name, component);
        } else static if (is(T == BinaryPackage)) {
            pkgList = sourceRepo.getBinaryPackages (conf.synchrotron.sourceSuite.name, component, arch);
        } else {
            assert (0);
        }

        auto pkgMap = getNewestPackagesMap (pkgList);
        return pkgMap;
    }

    /**
     * Import an arbitrary amount of packages via the archive management software.
     */
    private bool importPackageFiles (const string suite, const string component, const string[] fnames)
    {
        return dak.importPackageFiles (suite, component, fnames, importsTrusted, true);
    }

    /**
     * Import a source package from the source repository into the
     * target repo.
     */
    private bool importSourcePackage (SourcePackage spkg, string suite, string component)
    {
        string dscfile;
        foreach (file; spkg.files) {
            // the source repository might be on a remote location, so we need to
            // request each file to be there.
            // (dak will fetch the files referenced in the .dsc file from the same directory)
            if (file.fname.endsWith (".dsc"))
                dscfile = sourceRepo.getFile (file);
            sourceRepo.getFile (file);
        }

        if (dscfile.empty) {
            logError ("Critical consistency error: Source package %s in repository %s has no .dsc file.", spkg.name, sourceRepo.baseDir);
            return false;
        }

        return importPackageFiles (suite, component, [dscfile]);
    }

    /**
     * Import binary packages for the given set of source packages into the archive.
     */
    private bool importBinariesForSources (SourcePackage[] spkgs, string suite, string component)
    {
        if (!conf.synchrotron.syncBinaries) {
            logDebug ("Skipping binary syncs.");
            return true;
        }

        // list of valid architectrures supported by the target
        immutable targetArchs = conf.archive.incomingSuite.architectures.idup;

        // cache of binary-package mappings
        BinaryPackage[string][string] binPkgArchMap;
        foreach (ref arch; targetArchs) {
            binPkgArchMap[arch] = getSourceRepoPackageMap!BinaryPackage (component, arch);
        }

        foreach (ref spkg; spkgs) {
            foreach (ref arch; targetArchs) {
                if (arch !in binPkgArchMap)
                    continue;
                auto binPkgMap = binPkgArchMap[arch];

                auto binFiles = appender!(string[]);
                foreach (ref binI; parallel (spkg.binaries)) {
                    if (binI.name !in binPkgMap)
                        continue;
                    auto binPkg = binPkgMap[binI.name];
                    if (compareVersions (binI.ver, binPkg.ver) > 0) {
                        logInfo ("Not syncing binary package '%s': Version number '%s' is lower than the source package version '%s'.",
                                    binPkg.name, binPkg.ver, binI.ver);
                        continue;
                    }
                    // TODO: Handle Debian binNMUs better: Maybe strip the "+b1" suffix and then do *exact* version comparisons, to ensure
                    // that source and binary version are exactly the same, and we don't do bad binary syncs.

                    auto fname = sourceRepo.getFile (binPkg.file);
                    synchronized (this)
                        binFiles ~= fname;
                }

                // now import the binary packages, if there is anything to import
                if (binFiles.data.length == 0) {
                    logWarning ("Unable to sync any binary for source package %s/%s", spkg.name, spkg.ver);
                } else {
                    auto ret = importPackageFiles (suite, component, binFiles.data);
                    if (!ret)
                        return false;
                }
            }
        }

        return true;
    }

    bool syncPackages (const string component, const string[] pkgnames, bool force = false)
    in { assert (pkgnames.length > 0); }
    body
    {
        checkSyncReady ();
        immutable targetSuite = conf.archive.incomingSuite.name;

        auto destPkgs = targetRepo.getSourcePackages (targetSuite, component);
        auto destPkgMap = getNewestPackagesMap (destPkgs);
        auto srcPkgMap = getSourceRepoPackageMap!SourcePackage (component);

        auto syncedSrcPkgs = appender!(SourcePackage[]);
        foreach (pkgname; pkgnames) {
            auto spkgP = pkgname in srcPkgMap;
            auto dpkgP = pkgname in destPkgMap;

            if (spkgP is null) {
                logInfo ("Can not sync %s: Does not exist in source.", pkgname);
                continue;
            }

            auto spkg = *spkgP;
            if (dpkgP !is null) {
                if (compareVersions ((*dpkgP).ver, spkg.ver) >= 0) {
                    logInfo ("Can not sync %s: Target version '%s' is newer/equal than source version '%s'.",
                             pkgname, (*dpkgP).ver, spkg.ver);
                    continue;
                }
            }

            // sync source package
            // the source package must always be known to dak first
            auto ret = importSourcePackage (spkg, targetSuite, component);
            if (!ret)
                return false;
            syncedSrcPkgs ~= spkg;
        }

        auto ret = importBinariesForSources (syncedSrcPkgs.data, targetSuite, component);

        // TODO: Analyze the input, fetch the packages from the source distribution and
        // import them into the target in their correct order.
        // Then apply the correct, synced override from the source distro.

        return ret;
    }

    /**
     * Synchronize all packages that are newer
     */
    bool autosync ()
    {
        checkSyncReady ();
        immutable distroTag = conf.archive.distroTag;
        immutable targetSuite = conf.archive.incomingSuite.name;

        auto syncedSrcPkgs = appender!(SourcePackage[]);
        foreach (ref component; conf.archive.incomingSuite.components) {
            auto destPkgs = targetRepo.getSourcePackages (targetSuite, component);
            auto destPkgMap = getNewestPackagesMap (destPkgs);
            auto srcPkgMap = getSourceRepoPackageMap!SourcePackage (component);

            foreach (spkg; srcPkgMap.byValue) {
                auto dpkgP = spkg.name in destPkgMap;
                if (dpkgP !is null) {
                    auto dpkg = *dpkgP;

                    if (compareVersions ((*dpkgP).ver, spkg.ver) >= 0) {
                        logDebug ("Skipped sync of %s: Target version '%s' is newer/equal than source version '%s'.",
                                  spkg.name, (*dpkgP).ver, spkg.ver);
                        continue;
                    }

                    // check if we have a modified target package,
                    // indicated via its Debian revision, e.g. "1.0-0tanglu1"
                    if (dpkg.ver.getDebianRev.canFind (distroTag)) {
                        logInfo ("No syncing %s/%s: It has modifications.", spkg.name, spkg.ver);
                        continue;
                    }
                }

                // sync source package
                // the source package must always be known to dak first
                auto ret = importSourcePackage (spkg, targetSuite, component);
                if (!ret)
                    return false;
                syncedSrcPkgs ~= spkg;
            }

            // import binaries as well, if necessary
            auto ret = importBinariesForSources (syncedSrcPkgs.data, targetSuite, component);
            if (!ret)
                return false;
        }

        return true;
    }

}
