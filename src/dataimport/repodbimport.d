/*
 * Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
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

module datasync.repodbsync;
@safe:

import std.typecons : scoped;
import std.array : empty, appender;
import std.string : format;
import std.algorithm : canFind;
import std.path : buildPath;

import laniakea.logging;
import laniakea.localconfig;
import laniakea.repository;
import laniakea.db;
import laniakea.db.schema.archive;


private void experimental_SyncAppStreamData (Session session, Repository repo,
                                            string suiteName, string componentName, string archName,
                                            BinaryPackage[] binPackages) @trusted
{
    import appstream.c.types : FormatStyle, FormatKind, AsComponent, AsIcon, IconKind;
    import appstream.Metadata : Metadata;
    import laniakea.compressed : decompressFileToString;
    version(ExperimentalAppStream) import appstream.c.types : ParseFlags;


    immutable yamlFile = repo.getIndexFile (suiteName,
                                            buildPath (componentName, "dep11", "Components-%s.yml.xz".format (archName)));
    if (yamlFile.empty)
        return;
    immutable cidMapFile = repo.getIndexFile (suiteName,
                                            buildPath (componentName, "dep11", "CID-Index-%s.json.gz".format (archName)));
    if (cidMapFile.empty)
        return;

    auto cidMap = parseJsonString (decompressFileToString (cidMapFile), cidMapFile);

    immutable yamlCollectiondata = decompressFileToString (yamlFile);

    auto mdata = new Metadata;
    mdata.setLocale ("ALL");
    mdata.setFormatStyle (FormatStyle.COLLECTION);
    version(ExperimentalAppStream) mdata.setParseFlags(ParseFlags.IGNORE_MEDIABASEURL);
    mdata.parse (yamlCollectiondata, FormatKind.YAML);

    auto binPkgMap = getNewestPackagesMap (binPackages);

    auto cptArr = mdata.getComponents;
    if (cptArr.len == 0)
        return;

    logInfo ("Found %s software components in %s/%s", cptArr.len, suiteName, componentName);

    auto tmpMdata = new Metadata;
    tmpMdata.setLocale ("ALL");
    tmpMdata.setFormatStyle (FormatStyle.COLLECTION);

    for (uint i = 0; i < cptArr.len; i++) {
        // cast array data to D Component and keep a reference to the C struct
        auto cpt = scoped!ASComponent (cast (AsComponent*) cptArr.index (i));
        cpt.setActiveLocale ("C");

        immutable pkgname = cpt.getPkgname;
        if (pkgname.empty) {
            // we skip these for now, web-apps have no package assigned - we might need a better way to map
            // those to their packages, likely with an improved appstream-generator integration
            logDebug ("Found DEP-11 component without package name in %s/%s: %s", suiteName, componentName, cpt.getId);
            continue;
        }

        auto dbCpt = new SoftwareComponent;
        tmpMdata.clearComponents ();
        tmpMdata.addComponent (cpt);
        dbCpt.xml = tmpMdata.componentsToCollection (FormatKind.XML);
        dbCpt.updateUUID ();

        auto dbPkg = binPkgMap.get (cpt.getPkgname, null);
        auto existingCpt = session.createQuery ("FROM SoftwareComponent
                                                 WHERE uuid_s=:uuid")
                           .setParameter("uuid", dbCpt.uuid_s).uniqueResult!SoftwareComponent;
        if (existingCpt !is null) {
            if (dbPkg !is null) {
                if (!existingCpt.binPackages[].canFind (dbPkg)) {
                    existingCpt.binPackages ~= dbPkg;
                    session.update (existingCpt);
                }
            }
            continue; // we already have this component, no need to add it again
        }

        if (dbPkg is null) {
            logWarning ("Found orphaned DEP-11 component in %s/%s: %s", suiteName, componentName, cpt.getId);
            continue;
        }
        dbCpt.binPackages ~= dbPkg;

        string gcid;
        if (cpt.getId in cidMap)
            gcid = cidMap[cpt.getId].get!string;
        if (gcid.empty)
            logWarning ("Found DEP-11 component '%s' in %s/%s, but could not find a global ID for it.", cpt.getId, suiteName, componentName);

        dbCpt.kind = cpt.getKind;
        dbCpt.cid = cpt.getId;
        dbCpt.gcid = gcid;
        dbCpt.name = cpt.getName;
        dbCpt.summary = cpt.getSummary;
        dbCpt.description = cpt.getDescription;

        auto iconsArr = cpt.getIcons ();
        assert (iconsArr !is null);
        for (uint j = 0; j < iconsArr.len; j++) {
            import appstream.Icon : Icon;
            auto icon = scoped!Icon (cast (AsIcon*) iconsArr.index (j));

            if (icon.getKind () == IconKind.CACHED) {
                dbCpt.iconName = icon.getName ();
                break;
            }
        }

        dbCpt.projectLicense = cpt.getProjectLicense;
        dbCpt.developerName = cpt.getDeveloperName;

        auto catArr = cpt.getCategories;
        auto catAppender = appender!(string[]);
        for (uint j = 0; j < catArr.len; j++) {
            import std.string : fromStringz;
            import std.conv : to;

            catAppender ~=to!string ((cast(char*) catArr.index (j)).fromStringz);
        }
        dbCpt.categories = catAppender.data;

        session.save (dbCpt);
        logDebug ("Added new software component '%s' to database", dbCpt.cid);
    }
}

bool syncRepoData (string suiteName, string repoName = "master") @trusted
{
    import core.sys.posix.unistd : fork, pid_t;
    import core.sys.posix.sys.wait;
    import core.stdc.stdlib : exit;
    import std.exception : errnoEnforce;

    auto db = Database.get;

    auto sFactory = db.newSessionFactory ();
    scope (exit) sFactory.close ();
    auto session = sFactory.openSession ();
    scope (exit) session.close ();

    auto suite = session.getSuite (suiteName);
    if (suite is null) {
        logError ("Unable to find suite: %s", suiteName);
        return false;
    }

    Repository repo;
    if (repoName == "master") {
        repo = new Repository (LocalConfig.get.archive.rootPath, repoName);
        repo.setTrusted (true);
    } else {
        assert (0, "The multiple repositories feature is not yet implemented.");
    }

    // FIXME: Hibernated doesn't work well in multithreaded environments, therefore we fork here
    // to have some temporary parallelization. Ultimately, Hibernated needs to be fixed though.

    bool ret = true;
    foreach (ref component; suite.components) {
        // Source packages
        repo.getSourcePackages (suite.name, component.name, session, true);

        pid_t[] processes;
        foreach (ref arch; suite.architectures) {
            pid_t pid = fork ();
            errnoEnforce (pid >= 0, "Fork failed");

            if (pid == 0) {
                // child process
                logDebug ("Child process forked.");

                auto childDb = Database.get;
                auto childSFactory = childDb.newSessionFactory ();
                scope (exit) childSFactory.close ();
                auto childSession = childSFactory.openSession ();
                scope (exit) childSession.close ();

                // binary packages
                auto binPackages = repo.getBinaryPackages (suite.name,
                                                           component.name,
                                                           arch.name,
                                                           childSession,
                                                           true);

                // binary packages of the debian-installer
                repo.getInstallerPackages (suite.name,
                                           component.name,
                                           arch.name,
                                           childSession,
                                           true);

                // Experimental AppStream netadata sync
                version (ExperimentalAppStream)
                experimental_SyncAppStreamData (session,
                                                repo,
                                                suite.name,
                                                component.name,
                                                arch.name,
                                                binPackages);

                exit (0);
            }

            processes ~= pid;
        }

        foreach (pid; processes) {
            int status = 0;
            do {
                errnoEnforce (waitpid (pid, &status, 0) != -1, "Waitpid failed");
            } while (!WIFEXITED (status));

            if (WEXITSTATUS (status) != 0)
                ret = false;
        }

        if (!ret)
            break;
    }

    return ret;
}
