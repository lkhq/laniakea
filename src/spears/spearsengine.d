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

import std.array : empty, array, join;
import std.string : format, startsWith, strip, split;
import std.algorithm : canFind, map, filter, sort;
import std.path : buildPath, baseName, dirName;
import std.array : appender;
import std.typecons : Tuple;
import std.parallelism : parallel;
static import std.file;
import containers : HashMap;

import laniakea.repository.dak;
import laniakea.db.schema.archive;
import laniakea.localconfig;
import laniakea.logging;
import laniakea.db;

import spears.britneyconfig;
import spears.britney;
import spears.excuses;

/**
 * Run package migrations using Britney and manage its configurations.
 */
class SpearsEngine
{

private:

    Britney britney;
    Dak dak;

    Database db;
    SessionFactory sFactory;

    BaseConfig baseConf;
    SpearsConfig spearsConf;
    LocalConfig localConf;

    immutable string workspace;

public:

    this ()
    {
        britney = new Britney ();
        dak = new Dak ();

        db = Database.get;
        sFactory = db.newSessionFactory! (SpearsExcuse);

        baseConf = db.getBaseConfig;
        spearsConf = db.getSpearsConfig;

        localConf = LocalConfig.get;
        workspace = buildPath (localConf.workspace, "spears");
        std.file.mkdirRecurse (workspace);
    }

    alias SuiteCheckResult = Tuple!(ArchiveSuite[], "from", ArchiveSuite, "to", bool, "error");
    private SuiteCheckResult suitesFromConfigEntry (Session session, SpearsConfigEntry centry)
    {
        SuiteCheckResult res;
        res.error = false;

        foreach (suiteName; centry.sourceSuites) {
            auto maybeSuite = session.getSuite (suiteName);
            if (maybeSuite is null) {
                logError ("Migration source suite '%s' does not exist. Can not create configuration.", suiteName);
                res.error = true;
                return res;
            }
            res.from ~= maybeSuite;
        }

        auto maybeSuite = session.getSuite (centry.targetSuite);
        if (maybeSuite is null) {
            logError ("Migration target suite '%s' does not exist. Can not create configuration.", centry.targetSuite);
            res.error = true;
            return res;
        }
        res.to = maybeSuite;

        if (res.from.canFind (res.to)) {
            logError ("Migration target suite (%s) is contained in source suite list.", res.to.name);
            res.error = true;
            return res;
        }

        return res;
    }

    private string getMigrationId (ArchiveSuite[] suitesFrom, string suiteTo)
    {
        return "%s-to-%s".format (suitesFrom.map! (s => s.name).array.sort.join ("+"), suiteTo);
    }

    private string getMigrationName (ArchiveSuite[] suitesFrom, ArchiveSuite suiteTo)
    {
        return "%s -> %s".format (suitesFrom.map! (s => s.name).array.sort.join ("+"), suiteTo.name);
    }

    private string getMigrateWorkspace (ArchiveSuite[] suitesFrom, string suiteTo)
    {
        return buildPath (workspace, getMigrationId (suitesFrom, suiteTo));
    }

    /**
     * If our source suite is a single suite, we can just use the archive's vanilla dists/
     * directory as source of package information for Britnay.
     * If we use Britney to migrate packages from two suites together however, we need
     * an amalgamation of the two suites' Packages/Sources files, which resides in Britney's
     * workspace directory.
     * This function returns the correct dists/ path, depending on the case.
     */
    private string getSourceSuiteDistsDir (string miWorkspace, ArchiveSuite[] sourceSuites)
    {
        import std.file : mkdirRecurse;

        if (sourceSuites.length == 1) {
            immutable archiveRootPath = localConf.archive.rootPath;
            return buildPath (archiveRootPath, "dists", sourceSuites[0].name);
        }

        auto distsDir = buildPath (miWorkspace, "input", "dists", sourceSuites.map! (s => s.name).join ("+"));
        mkdirRecurse (distsDir);
        return distsDir;
    }

    bool updateConfig ()
    {
        logInfo ("Updating configuration");

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        immutable archiveRootPath = localConf.archive.rootPath;
        foreach (ref mentry; spearsConf.migrations.byValue) {
            auto scRes = suitesFromConfigEntry (session, mentry);
            if (scRes.error)
                continue;
            auto fromSuites = scRes.from;
            auto toSuite = scRes.to;
            assert (fromSuites.length >= 1);

            logInfo ("Refreshing Britney config for '%s'", getMigrationName (fromSuites, toSuite));
            immutable miWorkspace = getMigrateWorkspace (fromSuites, toSuite.name);
            auto bc = new BritneyConfig (miWorkspace);

            bc.setArchivePaths (getSourceSuiteDistsDir (miWorkspace, fromSuites),
                                buildPath (archiveRootPath, "dists", toSuite.name));
            bc.setComponents (map!(c => c.name)(toSuite.components[]).array);
            bc.setArchitectures (array (toSuite.architectures[]
                                               .map! (a => a.name)
                                               .filter! (a => a != "all")));
            bc.setDelays (mentry.delays);
            bc.setHints (mentry.hints);

            bc.save ();
        }

        logInfo ("Updating Britney");
        britney.updateDist ();

        return true;
    }

    /**
     * If there is more than one source suite, we need to give britney an amalgamation
     * of the data of the two source suites.
     * This function prepares this data.
     */
    private void prepareSourceData (string miWorkspace, ArchiveSuite[] sourceSuites, ArchiveSuite targetSuite)
    {
        import std.file : exists;
        import laniakea.compressed : decompressFile, compressAndSave, ArchiveType;

        // only one suite means we can use the suite's data directky
        if (sourceSuites.length <= 1)
            return;

        immutable archiveRootPath = localConf.archive.rootPath;
        immutable fakeDistsDir = getSourceSuiteDistsDir (miWorkspace, sourceSuites);

        foreach (ref component; targetSuite.components) {
            import std.path : dirName;
            import std.file : mkdirRecurse, exists;

            foreach (arch; parallel (array (targetSuite.architectures))) {
                string[] packagesFiles;

                foreach (ref installerDir; ["", "debian-installer"]) {
                    foreach (ref sourceSuite; sourceSuites) {
                        immutable pfile = buildPath (archiveRootPath,
                                                    "dists",
                                                    sourceSuite.name,
                                                    component.name,
                                                    installerDir,
                                                    "binary-%s".format (arch.name),
                                                    "Packages.xz");

                        if (pfile.exists) {
                            logDebug ("Looking for packages in: %s", pfile);
                            packagesFiles ~= pfile;
                        }
                    }

                    if (packagesFiles.empty && installerDir.empty)
                        throw new Exception ("No packages found on %s/%s in sources for migration '%s': Can not continue."
                                                .format (component.name,
                                                        arch.name,
                                                        getMigrationId (sourceSuites, targetSuite.name)));

                    // create new merged Packages file
                    immutable targetPackagesFile = buildPath (fakeDistsDir,
                                                            component.name,
                                                            installerDir,
                                                            "binary-%s".format (arch.name),
                                                            "Packages.xz");
                    logDebug ("Generating combined new fake packages file: %s", targetPackagesFile);
                    mkdirRecurse (targetPackagesFile.dirName);
                    auto data = appender!(ubyte[]);
                    foreach (fname; packagesFiles)
                        data ~= decompressFile (fname);
                    compressAndSave (data.data, targetPackagesFile, ArchiveType.XZ);
                }
            }

            string[] sourcesFiles;
            foreach (ref sourceSuite; sourceSuites) {
                immutable sfile = buildPath (archiveRootPath,
                                             "dists",
                                             sourceSuite.name,
                                             component.name,
                                             "source",
                                             "Sources.xz");
                if (sfile.exists) {
                    logDebug ("Looking for source packages in: %s", sfile);
                    sourcesFiles ~= sfile;
                }
            }

            if (sourcesFiles.empty)
                throw new Exception ("No source packages found in '%s' sources for migration '%s': Can not continue."
                                     .format (component.name, getMigrationId (sourceSuites, targetSuite.name)));

            // Create new merged Sources file
            immutable targetSourcesFile = buildPath (fakeDistsDir,
                                                     component.name,
                                                     "source",
                                                     "Sources.xz");
            logDebug ("Generating combined new fake sources file: %s", targetSourcesFile);
            mkdirRecurse (targetSourcesFile.dirName);
            auto data = appender!(ubyte[]);
            foreach (fname; sourcesFiles)
                data ~= decompressFile (fname);
            compressAndSave (data.data, targetSourcesFile, ArchiveType.XZ);
        }

        // Britney needs a Release file to determine the source suites components and architectures.
        // To keep things simple, we just copy one of the source Release files.
        // TODO: Synthesis a dedicated file instead and be less lazy
        immutable releaseFile = buildPath (archiveRootPath,
                                                 "dists",
                                                 sourceSuites[0].name,
                                                 "Release");
        immutable targetReleaseFile = buildPath (fakeDistsDir, "Release");
        logDebug ("Using Release file for fake suite: %s", releaseFile);
        if (targetReleaseFile.exists)
            std.file.remove (targetReleaseFile);
        std.file.copy (releaseFile, targetReleaseFile);
    }

    private void collectUrgencies (string miWorkspace)
    {
        import std.file;
        import std.stdio : File;

        auto urgencies = appender!string;
        foreach (DirEntry e; dirEntries (dak.urgencyExportDir, SpanMode.shallow, true)) {
            if (!e.isFile)
                continue;
            if (!e.name.baseName.startsWith ("install-urgencies"))
                continue;

            logDebug ("Reading urgencies from %s", e.name);
            urgencies ~= readText (e.name);
        }

        logInfo ("Writing urgency policy file.");
        immutable urgencyPolicyFile = buildPath (miWorkspace, "state", "age-policy-urgencies");
        auto f = File (urgencyPolicyFile, "w");
        f.writeln (urgencies.data);
        f.close ();
    }

    private void setupDates (string miWorkspace)
    {
        import std.stdio : File;

        immutable datesPolicyFile = buildPath (miWorkspace, "state", "age-policy-dates");
        if (std.file.exists (datesPolicyFile))
            return;

        logInfo ("Writing dates policy file.");
        // just make an empty file for now
        auto f = File (datesPolicyFile, "w");
        f.writeln ("");
        f.close ();
    }

    private void setupVarious (string miWorkspace)
    {
        import std.stdio : File;

        // set up some random files which we do not use at all currently
        immutable rcbugsPolicyFileU = buildPath (miWorkspace, "state", "rc-bugs-unstable");
        if (!std.file.exists (rcbugsPolicyFileU)) {
            logInfo ("Writing RC bugs policy file (source).");
            // just make an empty file for now
            auto f = File (rcbugsPolicyFileU, "w");
            f.write ("");
            f.close ();
        }

        immutable rcbugsPolicyFileT = buildPath (miWorkspace, "state", "rc-bugs-testing");
        if (!std.file.exists (rcbugsPolicyFileT)) {
            logInfo ("Writing RC bugs policy file (target).");
            // just make an empty file for now
            auto f = File (rcbugsPolicyFileT, "w");
            f.write ("");
            f.close ();
        }

        // there is no support for Piuparts yet, but Britney crashes without these files
        immutable piupartsFileU = buildPath (miWorkspace, "state", "piuparts-summary-unstable.json");
        if (!std.file.exists (piupartsFileU)) {
            logInfo ("Writing Piuparts summary file (source).");
            // just make an empty file for now
            auto f = File (piupartsFileU, "w");
            f.write ("");
            f.close ();
        }

        immutable piupartsFileT = buildPath (miWorkspace, "state", "piuparts-summary-testing.json");
        if (!std.file.exists (piupartsFileT)) {
            logInfo ("Writing Piuparts summary file (target).");
            // just make an empty file for now
            auto f = File (piupartsFileT, "w");
            f.write ("");
            f.close ();
        }
    }

    private string postprocessHeidiFile (string miWorkspace)
    {
        import std.stdio : File;
        immutable heidiResult = buildPath (miWorkspace, "output", "target", "HeidiResult");
        immutable processedResult = buildPath (miWorkspace, "output", "target", "heidi", "current");

        char[] buf;
        auto finalData = appender!(string[]);

        auto f = File (heidiResult, "r");
        while (f.readln (buf)) {
            auto parts = buf.strip.split (" ");
            if (parts.length != 4) {
                logWarning ("Found invalid line in Britney result: %s", buf.strip);
                continue;
            }
            finalData ~= "%s %s %s".format (parts[0], parts[1], parts[2]);
        }

        f.close ();
        std.file.mkdirRecurse (processedResult.dirName);
        f = File (processedResult, "w");
        foreach (ref line; finalData.data)
            f.writeln (line);
        f.close ();

        return processedResult;
    }

    private bool updateDatabase (Session session, string miWorkspace, ArchiveSuite[] fromSuites, ArchiveSuite toSuite)
    {
        import std.file : exists;
        import std.typecons : tuple;

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        immutable excusesYaml = buildPath (miWorkspace, "output", "target", "excuses.yaml");
        immutable logFile = buildPath (miWorkspace, "output", "target", "output.txt");

        if ((!excusesYaml.exists) || (!logFile.exists)) {
            conn.addEvent (EventKind.ERROR, "no-excuses-data", "Unable to find and process the excuses information. Spears data will be outdated.");
            return false;
        }

        ExcusesFile efile;
        if (fromSuites.length <= 1)
            efile = new ExcusesFile (excusesYaml, logFile, fromSuites[0].name, toSuite.name);
        else
            efile = new ExcusesFile (excusesYaml, logFile, null, toSuite.name);

        // get a unique identifier for this migration task
        immutable migrationId = getMigrationId (fromSuites, toSuite.name);

        // FIXME: we do the quick and dirty update here, if the performance of this is too bad one
        // day, it needs to be optimized to just update stuff that is needed.
        conn.removeSpearsExcusesForMigration (migrationId);

        // read repository information to match packages to their source suites before adding
        // their excuses to the database.
        // This is only needed for multi-source-suite combined migrations, otherwise there is only one
        // source suites packages can originate from.
        auto pkgSourceSuiteMap = HashMap!(string, string) (32);
        if (fromSuites.length > 1) {
            import laniakea.repository : Repository;

            // we need repository information to attribute packages to their right suites
            auto repo = new Repository (localConf.archive.rootPath,
                                        "master"); // FIXME: Use the correct repo vendor name here?
            repo.setTrusted (true);

            foreach (suite; fromSuites) {
                foreach (component; suite.components) {
                    foreach (spkg; repo.getSourcePackages (suite.name, component.name))
                        pkgSourceSuiteMap[spkg.name ~ "/" ~ spkg.ver] = suite.name;
                }
            }
        }

        // add excuses to database
        foreach (id, excuse; efile.getExcuses) {
            import std.uuid : randomUUID;
            excuse.uuid = randomUUID ();
            excuse.migrationId = migrationId;

            if (!pkgSourceSuiteMap.empty) {
                excuse.sourceSuite = pkgSourceSuiteMap.get (excuse.sourcePackage ~ "/" ~ excuse.newVersion, null);
                if (excuse.sourceSuite is null)
                    excuse.sourceSuite = pkgSourceSuiteMap.get (excuse.sourcePackage ~ "/" ~ excuse.oldVersion, "-");
            }

            session.save (excuse);
        }

        return true;
    }

    private bool runMigrationInternal (Session session, ArchiveSuite[] fromSuites, ArchiveSuite toSuite)
    {
        immutable miWorkspace = getMigrateWorkspace (fromSuites, toSuite.name);
        immutable britneyConf = buildPath (miWorkspace, "britney.conf");
        if (!std.file.exists (britneyConf)) {
            logWarning ("No Britney config for migration run '%s' - maybe the configuration was not yet updated?", getMigrationName (fromSuites, toSuite));
            return false;
        }

        logInfo ("Migration run for '%s'", getMigrationName (fromSuites, toSuite));
        // ensure prerequisites are met and Britney is fed with all the data it needs
        prepareSourceData (miWorkspace, fromSuites, toSuite);
        collectUrgencies (miWorkspace);
        setupDates (miWorkspace);
        setupVarious (miWorkspace);

        // execute the migration tester
        britney.run (britneyConf);

        // tell dak to import the new data (overriding the target suite)
        immutable heidiResult = postprocessHeidiFile (miWorkspace);
        auto ret = dak.setSuiteToBritneyResult (toSuite.name, heidiResult);

        // add the results to our database
        ret = updateDatabase (session, miWorkspace, fromSuites, toSuite) && ret;
        return ret;
    }

    bool runMigration (string fromSuiteStr, string toSuite)
    {
        bool done = false;
        bool ret = true;

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        foreach (ref mentry; spearsConf.migrations) {
            if ((mentry.sourceSuites.join ("+") == fromSuiteStr) && (mentry.targetSuite == toSuite)) {
                auto scRes = suitesFromConfigEntry (session, mentry);
                if (scRes.error)
                    continue;
                done = true;
                if (!runMigrationInternal (session, scRes.from, scRes.to))
                    ret = false;
            }
        }

        if (!done) {
            logError ("Unable to find migration setup for '%s -> %s'", fromSuiteStr, toSuite);
            return false;
        }

        return ret;
    }

    bool runMigration ()
    {
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        bool ret = true;
        foreach (ref mentry; spearsConf.migrations) {
            auto scRes = suitesFromConfigEntry (session, mentry);
            if (scRes.error)
                continue;

            if (!runMigrationInternal (session, scRes.from, scRes.to))
                ret = false;
        }

        return ret;
    }

}
