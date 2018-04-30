/*
 * Copyright (C) 2017-2018 Matthias Klumpp <matthias@tenstral.net>
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

module ariadne.buildscheduler;

import laniakea.logging;
import laniakea.db;
import laniakea.db.schema.archive;
import laniakea.utils : archMatches;
import containers : HashMap;

import std.array : empty;
import std.string : format;
import std.algorithm : canFind, equal, find;
import std.parallelism : parallel;

/**
 * Create an index of the most recent source packages, using
 * the source-UUID of source packages.
 */
auto getNewestSourcesIndex (Session session, ArchiveSuite suite)
{
    import laniakea.utils : compareVersions;

    auto srcPackages = HashMap!(UUID, SourcePackage) (64);
    auto q = session.createQuery ("FROM SourcePackage WHERE repo.id=:repoID")
                    .setParameter ("repoID", suite.repo.id);
    foreach (spkg; q.list!SourcePackage) {
        if (spkg.suites[].canFind (suite)) {
            auto epkgP = spkg.sourceUUID in srcPackages;
            if (epkgP !is null) {
                auto epkg = *epkgP;
                // don't override if the existing version is newer
                if (compareVersions (spkg.ver, epkg.ver) <= 0)
                    continue;
            }

            srcPackages[spkg.sourceUUID] = spkg;
        }
    }

    return srcPackages;
}

/**
 * Get list of binary packages built for the given source package.
 */
auto binariesForPackage (Session session, ArchiveRepository repo,
                         const string sourceName, const string sourceVersion, ArchiveArchitecture arch)
{
    auto q = session.createQuery ("FROM BinaryPackage WHERE repo.id=:repoID
                                     AND sourceName=:name
                                     AND sourceVersion=:version
                                     AND architecture.id=:archID")
                    .setParameter ("repoID", repo.id)
                    .setParameter ("name", sourceName)
                    .setParameter ("version", sourceVersion)
                    .setParameter ("archID", arch.id);
    return q.list!BinaryPackage;
}

/**
 * Get Debcheck issues related to the given source package.
 */
auto debcheckIssuesForPackage (Session session, const string suiteName,
                               const string packageName, const string packageVersion, ArchiveArchitecture arch)
{
    auto q = session.createQuery ("FROM DebcheckIssue WHERE packageKind_i=:kind
                                     AND suiteName=:suite
                                     AND packageName=:name
                                     AND packageVersion=:version
                                     AND architecture=:arch")
                    .setParameter ("kind", PackageType.SOURCE)
                    .setParameter ("suite", suiteName)
                    .setParameter ("name", packageName)
                    .setParameter ("version", packageVersion)
                    .setParameter ("arch", arch.name);
    return q.list!DebcheckIssue;
}

/**
 * Schedule a job for the given architecture, if the
 * package can be built on it and no prior job was scheduled.
 */
bool scheduleBuildForArch (Connection conn, Session session, SourcePackage spkg, ArchiveArchitecture arch,
                           ArchiveSuite incomingSuite, bool simulate)
{
    // check if we can build the package on the current architecture
    if (!spkg.architectures.archMatches (arch.name))
        return false;

    // check if we have already scheduled a job for this in the past and don't create
    // another one in that case
    auto jobs = conn.getJobsByTriggerVerArch (spkg.sourceUUID, spkg.ver, arch.name, 0);
    if (jobs.length > 0)
        return false;

    // check if this package has binaries on already, in that case we don't
    // need a rebuild.
    auto bins = session.binariesForPackage (incomingSuite.repo, spkg.name, spkg.ver, arch);
    if (bins.length > 0)
        return false;

    // we have no binaries, looks like we might need to schedule a build job
    // check if all dependencies are there
    auto issues = session.debcheckIssuesForPackage (incomingSuite.name,
                                                    spkg.name, spkg.ver, arch);
    if (issues.length > 0)
        return false;

    // no issues found and a build seems required.
    // let's go!
    if (simulate) {
        logInfo ("New job for %s on %s", spkg.stringId, arch.name);
    } else {
        Job job;
        job.ver = spkg.ver;
        job.architecture = arch.name;
        conn.addJob (job,
                     LkModule.ARIADNE,
                     JobKind.PACKAGE_BUILD,
                     spkg.sourceUUID);
    }

    return true;
}

/**
 * Clean up jobs thet were scheduled for source packages that have meanwhile been removed from
 * the archive entirely.
 */
void deleteOrphanedJobs (Connection conn, Session session, bool simulate)
{
    auto pendingJobs = getPendingJobs (conn, LkModule.ARIADNE, 0);
    foreach (ref job; pendingJobs) {
        auto spkg = session.getSourcePackageForJob (job);
        if (spkg is null) {
            // we have no source package for this job, so this job is orphaned and can never be processed.
            // This happens if a job is scheduled for a package, and then the package is removed entirely from
            // all archive suites while the job has not finished yet.
            if (simulate)
                logInfo ("Delete orphaned job for %s (%s)", spkg.stringId, job.uuid.toString);
            else
                conn.deleteJob (job.uuid);
        }
    }
}

/**
 * Schedule builds for packages in the incoming suite.
 */
bool scheduleBuilds (bool simulate = false, string limitArchitecture = null, long limitCount = 0)
{
    auto db = Database.get;
    auto sFactory = db.newSessionFactory! (DebcheckIssue);
    scope (exit) sFactory.close ();
    auto session = sFactory.openSession ();
    scope (exit) session.close ();
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    const baseConfig = db.getBaseConfig ();
    immutable incomingSuiteName = baseConfig.archive.incomingSuite;

    if (incomingSuiteName.empty)
        throw new Exception("No incoming suite is set in base config.");
    auto incomingSuite = session.getSuite (incomingSuiteName);
    if (incomingSuite is null)
        throw new Exception("Incoming suite %s was not found in database.".format (incomingSuiteName));

    auto srcPackages = session.getNewestSourcesIndex (incomingSuite);

    ArchiveArchitecture archAll;
    foreach (ref arch; incomingSuite.architectures) {
        if (arch.name == "all") {
            archAll = arch;
            break;
        }
    }
    if (archAll is null)
        logWarning ("Suite '%s' does not have arch:all in its architecture set, some packages can not be built.", incomingSuite.name);

    if (simulate)
        logInfo ("Simulation, not scheduling any actual builds.");
    if (!limitArchitecture.empty)
        logInfo ("Only scheduling builds for architecture '%s'.", limitArchitecture);
    if (limitCount > 0)
        logInfo ("Only scheduling maximally %s builds.", limitCount);

    long scheduledCount = 0;
    foreach (ref spkg; srcPackages.byValue) {
        // if the package is arch:all only, it needs a dedicated build job
        if (spkg.architectures.equal (["all"])) {
            if (archAll is null)
                continue;

            if (!limitArchitecture.empty) {
                if (archAll.name != limitArchitecture)
                    continue; // Skip, we are not scheduling builds for arch:all
            }

            if (scheduleBuildForArch (conn, session, spkg, archAll, incomingSuite, simulate))
                scheduledCount++;

            if ((limitCount > 0) && (scheduledCount >= limitCount))
                break;
            continue;
        }

        foreach (ref arch; incomingSuite.architectures) {
            // The pseudo-architecture arch:all is treated specially
            if (arch.name == "all")
                continue;
            if (!limitArchitecture.empty) {
                if (arch.name != limitArchitecture)
                    continue; // Skip, we are not scheduling builds for this architecture
            }

            if (scheduleBuildForArch (conn, session, spkg, arch, incomingSuite, simulate))
                scheduledCount++;

            if ((limitCount > 0) && (scheduledCount >= limitCount))
                break;
        }

        if ((limitCount > 0) && (scheduledCount >= limitCount))
            break;
    }

    // cleanup
    conn.deleteOrphanedJobs (session, simulate);

    logDebug ("Scheduled %s build jobs.", scheduledCount);

    return true;
}
