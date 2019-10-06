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
import std.typecons : Tuple, Nullable;
import std.parallelism : parallel;
static import std.file;

import lknative.repository.dak;
import lknative.repository.types;
import lknative.logging;
import lknative.config : BaseConfig, SpearsConfig, SuiteInfo;
import lknative.config.spears;
import lknative.tagfile : TagFile;

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

    BaseConfig baseConf;
    SpearsConfig spearsConf;
    SuiteInfo[] archiveSuites;

    immutable string workspace;

public:

    this (BaseConfig bConfig, SpearsConfig sConfig, SuiteInfo[] allSuites)
    {
        britney = new Britney (bConfig, sConfig.britneyGitOriginUrl);
        dak = new Dak ();

        baseConf = bConfig;
        spearsConf = sConfig;

        workspace = buildPath (baseConf.workspace, "spears");
        std.file.mkdirRecurse (workspace);

        archiveSuites = allSuites;
    }

    private auto findSuiteByName (string suiteName)
    {
        Nullable!SuiteInfo suite;
        foreach (ref si; archiveSuites) {
            if (si.name == suiteName) {
                suite = si;
                break;
            }
        }

        return suite;
    }

    alias SuiteCheckResult = Tuple!(SuiteInfo[], "from", SuiteInfo, "to", bool, "error");
    private SuiteCheckResult suitesFromConfigEntry (SpearsConfigEntry centry)
    {
        SuiteCheckResult res;
        res.error = false;

        foreach (suiteName; centry.sourceSuites) {
            auto maybeSuite = findSuiteByName (suiteName);
            if (maybeSuite.isNull) {
                logError ("Migration source suite '%s' does not exist. Can not create configuration.", suiteName);
                res.error = true;
                return res;
            }
            res.from ~= maybeSuite;
        }

        auto maybeSuite = findSuiteByName (centry.targetSuite);
        if (maybeSuite.isNull) {
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

    private string getMigrationId (SuiteInfo[] suitesFrom, string suiteTo)
    {
        return "%s-to-%s".format (suitesFrom.map! (s => s.name).array.sort.join ("+"), suiteTo);
    }

    private string getMigrationName (SuiteInfo[] suitesFrom, SuiteInfo suiteTo)
    {
        return "%s -> %s".format (suitesFrom.map! (s => s.name).array.sort.join ("+"), suiteTo.name);
    }

    private string getMigrateWorkspace (SuiteInfo[] suitesFrom, string suiteTo)
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
    private string getSourceSuiteDistsDir (string miWorkspace, SuiteInfo[] sourceSuites)
    {
        import std.file : mkdirRecurse;

        if (sourceSuites.length == 1) {
            immutable archiveRootPath = baseConf.archive.rootPath;
            return buildPath (archiveRootPath, "dists", sourceSuites[0].name);
        }

        auto distsDir = buildPath (miWorkspace, "input", "dists", sourceSuites.map! (s => s.name).join ("+"));
        mkdirRecurse (distsDir);
        return distsDir;
    }

    bool updateConfig ()
    {
        logInfo ("Updating configuration");

        immutable archiveRootPath = baseConf.archive.rootPath;
        foreach (ref mentry; spearsConf.migrations.byValue) {
            auto scRes = suitesFromConfigEntry (mentry);
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
            bc.setComponents (toSuite.components);
            bc.setArchitectures (array (toSuite.architectures[]
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
    private void prepareSourceData (string miWorkspace, SuiteInfo[] sourceSuites, SuiteInfo targetSuite)
    {
        import std.file : exists;
        import lknative.compressed : decompressFile, compressAndSave, ArchiveType;

        // only one suite means we can use the suite's data directly
        if (sourceSuites.length <= 1)
            return;

        immutable archiveRootPath = baseConf.archive.rootPath;
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
                                                    component,
                                                    installerDir,
                                                    "binary-%s".format (arch),
                                                    "Packages.xz");

                        if (pfile.exists) {
                            logDebug ("Looking for packages in: %s", pfile);
                            packagesFiles ~= pfile;
                        }
                    }

                    if (packagesFiles.empty && installerDir.empty)
                        throw new Exception ("No packages found on %s/%s in sources for migration '%s': Can not continue."
                                                .format (component,
                                                        arch,
                                                        getMigrationId (sourceSuites, targetSuite.name)));

                    // create new merged Packages file
                    immutable targetPackagesFile = buildPath (fakeDistsDir,
                                                            component,
                                                            installerDir,
                                                            "binary-%s".format (arch),
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
                                             component,
                                             "source",
                                             "Sources.xz");
                if (sfile.exists) {
                    logDebug ("Looking for source packages in: %s", sfile);
                    sourcesFiles ~= sfile;
                }
            }

            if (sourcesFiles.empty)
                throw new Exception ("No source packages found in '%s' sources for migration '%s': Can not continue."
                                     .format (component, getMigrationId (sourceSuites, targetSuite.name)));

            // Create new merged Sources file
            immutable targetSourcesFile = buildPath (fakeDistsDir,
                                                     component,
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

    /**
     * If we have a partial source and target suite, we need to let Britney know about the
     * parent packages somehow.
     * At the moment, we simply abuse the FauxPackages system for that.
     */
    private void createFauxPackages (string miWorkspace, SuiteInfo[] sourceSuites, SuiteInfo targetSuite)
    {
        import std.stdio : File;

        // we don't support more than one source suite for this feature at the moment
        if (sourceSuites.length > 1) {
            logInfo("Not auto-generating faux packages: Multiple suites set as sources.");
            return;
        }
        auto sourceSuite = sourceSuites[0];

        if (!sourceSuite.parent.name.empty && !targetSuite.parent.name.empty) {
            logInfo("Creating faux-packages to aid resolving of partial suites.");
        } else {
            logInfo("No auto-generating faux packages: No source and target suite parents, generation is unnecessary.");
            return;
        }

        immutable archiveRootPath = baseConf.archive.rootPath;
        immutable fauxPkgFname = buildPath (miWorkspace, "input", "faux-packages");

        string[string] fauxPkgData;
        foreach (ref component; targetSuite.parent.components) {
            import std.path : dirName;
            import std.file : mkdirRecurse, exists;

            foreach (arch; parallel (array (targetSuite.parent.architectures))) {
                immutable pfile = buildPath (archiveRootPath,
                                             "dists",
                                             targetSuite.parent.name,
                                             component,
                                             "binary-%s".format (arch), "Packages.xz");

                if (!pfile.exists)
                    continue;

                logDebug ("Reading data for faux packages list: %s", pfile);
                auto tf = new TagFile;
                tf.open (pfile);

                do {
                    immutable pkgname = tf.readField ("Package");
                    immutable pkgversion = tf.readField ("Version");
                    immutable pkgarch = tf.readField ("Architecture");
                    immutable id = "%s-%s-%s".format (pkgname, pkgversion, pkgarch);
                    if (id in fauxPkgData)
                        continue;
                    immutable provides = tf.readField ("Provides", "");

                    auto data = "Package: %s\nVersion: %s".format (pkgname, pkgversion);
                    if ((!pkgarch.empty) && (pkgarch != "all"))
                        data ~= "\nArchitecture: %s".format (pkgarch);
                    if (!provides.empty)
                        data ~= "\nProvides: %s".format (provides);
                    if (component != "main")
                        data ~= "\nComponent: %s".format (component);

                    synchronized fauxPkgData[id] = data;
                } while (tf.nextSection ());
            }
        }

        auto f = File (fauxPkgFname, "w");
        foreach (ref segment; fauxPkgData.byValue) {
            f.writeln (segment ~ "\n");
        }
        f.close ();
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

    private void setupVarious (string miWorkspace, SuiteInfo[] sourceSuites, SuiteInfo targetSuite)
    {
        import std.stdio : File;

        // set up some random files which we do not use at all currently
        foreach (ref si; sourceSuites) {
            immutable rcbugsPolicyFileU = buildPath (miWorkspace, "state", "rc-bugs-%s".format (si.name));
            if (!std.file.exists (rcbugsPolicyFileU)) {
                logInfo ("Writing RC bugs policy file (source).");
                 // just make an empty file for now
                auto f = File (rcbugsPolicyFileU, "w");
                f.write ("");
                f.close ();
            }
        }

        immutable rcbugsPolicyFileT = buildPath (miWorkspace, "state", "rc-bugs-%s".format (targetSuite.name));
        if (!std.file.exists (rcbugsPolicyFileT)) {
            logInfo ("Writing RC bugs policy file (target).");
            // just make an empty file for now
            auto f = File (rcbugsPolicyFileT, "w");
            f.write ("");
            f.close ();
        }

        // there is no support for Piuparts yet, but Britney crashes without these files
        foreach (ref si; sourceSuites) {
            immutable piupartsFileU = buildPath (miWorkspace, "state", "piuparts-summary-%s.json".format (si.name));
            if (!std.file.exists (piupartsFileU)) {
                logInfo ("Writing Piuparts summary file (source).");
                // just make an empty file for now
                auto f = File (piupartsFileU, "w");
                f.write ("");
                f.close ();
            }
        }

        immutable piupartsFileT = buildPath (miWorkspace, "state", "piuparts-summary-%s.json".format (targetSuite.name));
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

    private auto retrieveExcuses (string miWorkspace, SuiteInfo[] fromSuites, SuiteInfo toSuite)
    {
        import std.file : exists;
        import std.typecons : tuple;

        Nullable!(SpearsExcuse[]) res;

        immutable excusesYaml = buildPath (miWorkspace, "output", "target", "excuses.yaml");
        immutable logFile = buildPath (miWorkspace, "output", "target", "output.txt");

        if ((!excusesYaml.exists) || (!logFile.exists)) {
            throw new Exception ("Unable to find and process the excuses information. Spears data will be outdated.");
        }

        ExcusesFile efile;
        if (fromSuites.length <= 1)
            efile = new ExcusesFile (excusesYaml, logFile, fromSuites[0].name, toSuite.name);
        else
            efile = new ExcusesFile (excusesYaml, logFile, null, toSuite.name);

        // get a unique identifier for this migration task
        immutable migrationId = getMigrationId (fromSuites, toSuite.name);

        // read repository information to match packages to their source suites before adding
        // their excuses to the database.
        // This is only needed for multi-source-suite combined migrations, otherwise there is only one
        // source suites packages can originate from.
        string[string] pkgSourceSuiteMap;
        if (fromSuites.length > 1) {
            import lknative.repository : Repository;

            // we need repository information to attribute packages to their right suites
            auto repo = new Repository (baseConf.archive.rootPath,
                                        baseConf.cacheDir,
                                        "master"); // FIXME: Use the correct repo vendor name here?
            repo.setTrusted (true);

            foreach (suite; fromSuites) {
                foreach (component; suite.components) {
                    foreach (spkg; repo.getSourcePackages (suite.name, component))
                        pkgSourceSuiteMap[spkg.name ~ "/" ~ spkg.ver] = suite.name;
                }
            }
        }
        pkgSourceSuiteMap.rehash ();

        auto excuses = appender!(SpearsExcuse[]);
        foreach (id, excuse; efile.getExcuses) {
            excuse.migrationId = migrationId;
            excuses ~= excuse;
        }

        res = excuses.data;

        return res;
    }

    private auto runMigrationInternal (SuiteInfo[] fromSuites, SuiteInfo toSuite)
    {
        Nullable!(SpearsExcuse[]) res;

        immutable miWorkspace = getMigrateWorkspace (fromSuites, toSuite.name);
        immutable britneyConf = buildPath (miWorkspace, "britney.conf");
        if (!std.file.exists (britneyConf)) {
            logWarning ("No Britney config for migration run '%s' - maybe the configuration was not yet updated?", getMigrationName (fromSuites, toSuite));
            return res;
        }

        logInfo ("Migration run for '%s'", getMigrationName (fromSuites, toSuite));
        // ensure prerequisites are met and Britney is fed with all the data it needs
        prepareSourceData (miWorkspace, fromSuites, toSuite);
        createFauxPackages (miWorkspace, fromSuites, toSuite);
        collectUrgencies (miWorkspace);
        setupDates (miWorkspace);
        setupVarious (miWorkspace, fromSuites, toSuite);

        // execute the migration tester
        britney.run (britneyConf);

        // tell dak to import the new data (overriding the target suite)
        immutable heidiResult = postprocessHeidiFile (miWorkspace);
        auto ret = dak.setSuiteToBritneyResult (toSuite.name, heidiResult);

        if (!ret)
            return res;

        res = retrieveExcuses (miWorkspace, fromSuites, toSuite);
        return res;
    }

    Tuple!(bool, SpearsExcuse[])
    runMigration (string fromSuiteStr, string toSuite)
    {
        bool done = false;

        Tuple!(bool, SpearsExcuse[]) res;
        res[0] = true;

        foreach (ref mentry; spearsConf.migrations) {
            if ((mentry.sourceSuites.join ("+") == fromSuiteStr) && (mentry.targetSuite == toSuite)) {
                auto scRes = suitesFromConfigEntry (mentry);
                if (scRes.error)
                    continue;
                done = true;
                auto excuses = runMigrationInternal (scRes.from, scRes.to);
                if (excuses.isNull)
                    res[0] = false;
                else
                    res[1] = excuses.get;
            }
        }

        if (!done) {
            logError ("Unable to find migration setup for '%s -> %s'", fromSuiteStr, toSuite);
            res[0] = false;
        }

        return res;
    }

}
