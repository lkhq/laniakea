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

import laniakea.repository;
import laniakea.repository.dak;
import laniakea.packages;
import laniakea.utils : compareVersions, getDebianRev;
import laniakea.config;
import laniakea.logging;

/**
 * Thrown on a package sync error.
 */
class PackageSyncError : Error
{
    @safe pure nothrow
    this (string msg, string file = __FILE__, size_t line = __LINE__, Throwable next = null)
    {
        super( msg, file, line, next );
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

        // the repository of the distribution we use to sync stuff from
        sourceRepo = new Repository (conf.synchrotron.sourceRepoUrl,
                                     conf.synchrotron.sourceName);
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
    private SourcePackage[string] getSourceRepoPackageMap (string component)
    {
        auto srcPkgs = sourceRepo.getSourcePackages (conf.synchrotron.sourceSuite.name, component);
        auto srcPkgMap = getNewestPackagesMap (srcPkgs);
        return srcPkgMap;
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
                dscfile = file.fname;
            sourceRepo.getFile (file);
        }

        if (dscfile.empty) {
            logError ("Critical consistency error: Source package %s in repository %s has no .dsc file.", spkg.name, sourceRepo.baseDir);
            return false;
        }

        return importPackageFiles (suite, component, [dscfile]);
    }

    bool syncPackages (const string component, const string[] pkgnames, bool force = false)
    in {assert (pkgnames.length > 0); }
    body
    {
        checkSyncReady ();
        immutable targetSuite = conf.archive.incomingSuite.name;

        auto destPkgs = targetRepo.getSourcePackages (targetSuite, component);
        auto destPkgMap = getNewestPackagesMap (destPkgs);
        auto srcPkgMap = getSourceRepoPackageMap (component);

        foreach (pkgname; pkgnames) {
            auto spkgP = pkgname in srcPkgMap;
            auto dpkgP = pkgname in destPkgMap;

            if (spkgP is null) {
                logInfo ("Can not sync %s: Does not exist in source.", pkgname);
                continue;
            }

            auto spkg = *spkgP;
            if (dpkgP !is null) {
                if (compareVersions (spkg.ver, (*dpkgP).ver) >= 0) {
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
        }

        // TODO: Analyze the input, fetch the packages from the source distribution and
        // import them into the target in their correct order.
        // Then apply the correct, synced override from the source distro.

        return true;
    }

    /**
     * Synchronize all packages that are newer
     */
    bool autosync ()
    {
        checkSyncReady ();
        immutable distroTag = conf.archive.distroTag;
        immutable targetSuite = conf.archive.incomingSuite.name;

        foreach (ref component; conf.archive.incomingSuite.components) {
            auto destPkgs = targetRepo.getSourcePackages (targetSuite, component);
            auto destPkgMap = getNewestPackagesMap (destPkgs);
            auto srcPkgMap = getSourceRepoPackageMap (component);

            foreach (spkg; srcPkgMap.byValue) {
                auto dpkgP = spkg.name in destPkgMap;
                if (dpkgP !is null) {
                    if (compareVersions (spkg.ver, (*dpkgP).ver) >= 0) {
                        logDebug ("Skipped sync of %s: Target version '%s' is newer/equal than source version '%s'.",
                                  spkg.name, (*dpkgP).ver, spkg.ver);
                        continue;
                    }
                }
                auto dpkg = *dpkgP;

                // check if we have a modified target package,
                // indicated via its Debian revision, e.g. "1.0-0tanglu1"
                if (dpkg.ver.getDebianRev.canFind (distroTag)) {
                    logInfo ("No syncing %s/%s: It has modifications.", spkg.name, spkg.ver);
                    continue;
                }

                // sync source package
                // the source package must always be known to dak first
                auto ret = importSourcePackage (spkg, targetSuite, component);
                if (!ret)
                    return false;
            }
        }

        return true;
    }

}
