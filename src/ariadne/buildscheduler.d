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

import std.array : empty;
import std.string : format;
import std.algorithm : canFind;
import std.parallelism : parallel;


/**
 * Create an index of the most recent source packages, using
 * the source-UUID of source packages.
 */
auto getNewestSourcesIndex (Session session, ArchiveSuite suite)
{
    SourcePackage[UUID] srcPackages;
    auto q = session.createQuery ("FROM SourcePackage WHERE repo.id=:repoid")
                    .setParameter ("repoid", suite.repo.id);
    foreach (spkg; q.list!SourcePackage) {
        if (spkg.suites.canFind (suite))
            srcPackages[spkg.sourceUUID] = spkg;
    }

    return srcPackages;
}

/**
 * Get list of binary packages built for the given source package.
 */
auto binariesForPackage (Session session, ArchiveRepository repo, const string sourceName, const string sourceVersion,
                         ArchiveArchitecture arch)
{
    auto q = session.createQuery ("FROM BinaryPackage WHERE repo.id=:repoid
                                     AND sourceName=:name
                                     AND sourceVersion=:version
                                     AND architecture=:arch")
                    .setParameter ("repoid", repo.id)
                    .setParameter ("name", sourceName)
                    .setParameter ("version", sourceVersion)
                    .setParameter ("arch", arch);
    return q.list!BinaryPackage;
}

/**
 * Get Debcheck issues related to the given source package.
 */
auto debcheckIssuesForPackage (Session session, const string suiteName, const string packageName,
                               const string packageVersion, const string architecture)
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
                    .setParameter ("arch", architecture);
    return q.list!DebcheckIssue;
}

bool scheduleBuilds ()
{
    auto db = Database.get;
    auto sFactory = db.newSessionFactory! (DebcheckIssue);
    scope (exit) sFactory.close();
    auto session = sFactory.openSession ();
    scope (exit) session.close ();
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    const baseConfig = db.getBaseConfig ();
    immutable incomingSuiteName = baseConfig.archive.incomingSuite;

    if (incomingSuiteName.empty)
        throw new Exception ("No incoming suite is set in base config.");
    auto incomingSuite = session.getSuite (incomingSuiteName);
    if (incomingSuite is null)
        throw new Exception ("Incoming suite %s was not found in database.".format (incomingSuiteName));

    auto srcPackages = session.getNewestSourcesIndex (incomingSuite);

    foreach (ref spkg; srcPackages.byValue) {
        foreach (ref arch; incomingSuite.architectures) {
            // TODO: Don't ignore arch:all, treat it properly instead.
            if (arch.name == "all")
                continue;

            // check if we can build the package on the current architecture
            if (!spkg.architectures.archMatches (arch.name))
                continue;

            // check if we have already scheduled a job for this in the past and don't create
            // another one in that case
            auto jobs = conn.getJobsByTriggerVerArch (spkg.sourceUUID, spkg.ver, arch.name, 0);
            if (jobs.length > 0)
                continue;

            // check if this package has binaries on already, in that case we don't
            // need a rebuild.
            auto bins = session.binariesForPackage (incomingSuite.repo, spkg.name, spkg.ver, arch);
            if (bins.length > 0)
                continue;

            // we have no binaries, looks like we might need to schedule a build job
            // check if all dependencies are there
            auto issues = session.debcheckIssuesForPackage (incomingSuite.name, spkg.name, spkg.ver, arch.name);
            if (issues.length > 0)
                continue;

            // no issues found and a build seems required.
            // let's go!
            Job job;
            job.moduleName = LkModule.ARIADNE;
            job.kind = "package-build";
            job.ver = spkg.ver;
            job.architecture = arch.name;
            conn.addJob (job, spkg.sourceUUID);
        }
    }

    return true;
}
