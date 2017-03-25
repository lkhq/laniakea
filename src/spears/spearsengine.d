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
import std.string : format, startsWith, strip, split;
import std.algorithm : canFind;
import std.path : buildPath, baseName, dirName;
import std.array : appender;
import std.typecons : Tuple;
static import std.file;

import laniakea.repository.dak;
import laniakea.pkgitems;
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
        baseConf = db.getBaseConfig;
        spearsConf = db.getConfig!SpearsConfig;

        localConf = LocalConfig.get;
        workspace = buildPath (localConf.workspace, "spears");
        std.file.mkdirRecurse (workspace);
    }

    alias SuiteCheckResult = Tuple!(DistroSuite, "from", DistroSuite, "to", bool, "error");
    private SuiteCheckResult suitesFromConfigEntry (SpearsConfigEntry centry)
    {
        SuiteCheckResult res;
        res.error = false;

        auto maybeSuite = db.getSuite (centry.sourceSuite);
        if (maybeSuite.isNull) {
            logError ("Migration source suite '%s' does not exist. Can not create configuration.", centry.sourceSuite);
            res.error = true;
            return res;
        }
        res.from = maybeSuite.get ();

        maybeSuite = db.getSuite (centry.targetSuite);
        if (maybeSuite.isNull) {
            logError ("Migration target suite '%s' does not exist. Can not create configuration.", centry.targetSuite);
            res.error = true;
            return res;
        }
        res.to = maybeSuite.get ();

        if (res.from == res.to) {
            logError ("Migration source and target suite (%s) are the same.", res.from.name);
            res.error = true;
            return res;
        }

        return res;
    }

    private string getMigrateWorkspace (string suiteFrom, string suiteTo)
    {
        return buildPath (workspace, "%s-to-%s".format (suiteFrom, suiteTo));
    }

    bool updateConfig ()
    {
        logInfo ("Updating configuration");
        immutable archiveRootPath = localConf.archive.rootPath;
        foreach (ref mentry; spearsConf.migrations) {
            auto scRes = suitesFromConfigEntry (mentry);
            if (scRes.error)
                continue;
            auto fromSuite = scRes.from;
            auto toSuite = scRes.to;

            logInfo ("Refreshing Britney config for '%s -> %s'", fromSuite.name, toSuite.name);
            immutable miWorkspace = getMigrateWorkspace (fromSuite.name, toSuite.name);
            auto bc = new BritneyConfig (miWorkspace);

            bc.setArchivePaths (buildPath (archiveRootPath, "dists", fromSuite.name),
                                buildPath (archiveRootPath, "dists", toSuite.name));
            bc.setComponents (toSuite.components);
            bc.setArchitectures (toSuite.architectures);
            bc.setDelays (mentry.delays);

            bc.save ();
        }

        logInfo ("Updating Britney");
        britney.updateDist ();

        return true;
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

    private bool updateDatabase (string miWorkspace, DistroSuite fromSuite, DistroSuite toSuite)
    {
        import std.file : exists;
        immutable excusesYaml = buildPath (miWorkspace, "output", "target", "excuses.yaml");
        immutable logFile = buildPath (miWorkspace, "output", "target", "output.txt");

        if ((!excusesYaml.exists) || (!logFile.exists)) {
            db.addEvent (EventKind.ERROR, "no-excuses-data", "Unable to find and process the excuses information. Spears data will be outdated.");
            return false;
        }

        auto efile = new ExcusesFile (excusesYaml, logFile, fromSuite.name, toSuite.name);
        auto collExcuses = db.getCollection ("spears.excuses");
        // FIXME: we do the quick and dirty update here, if the performance of this is too bad one
        // day, it needs to be optimized to just update stuff that is needed.
        foreach (cur; collExcuses.find (["sourceSuite": fromSuite.name, "targetSuite": toSuite.name]))
            collExcuses.remove (cur);
        foreach (excuse; efile.getExcuses ().byValue) {
            excuse.id = db.newBsonId ();
            collExcuses.insert (excuse);
        }

        return true;
    }

    private bool runMigrationInternal (DistroSuite fromSuite, DistroSuite toSuite)
    {
        immutable miWorkspace = getMigrateWorkspace (fromSuite.name, toSuite.name);
        immutable britneyConf = buildPath (miWorkspace, "britney.conf");
        if (!std.file.exists (britneyConf)) {
            logWarning ("No Britney config for migration run '%s -> %s' - maybe the configuration was not yet updated?", fromSuite.name, toSuite.name);
            return false;
        }

        logInfo ("Migration run for '%s -> %s'", fromSuite.name, toSuite.name);
        // ensure prerequisites are met and Britney is fed with all the data it needs
        collectUrgencies (miWorkspace);
        setupDates (miWorkspace);
        setupVarious (miWorkspace);

        // execute the migration tester
        britney.run (britneyConf);

        // tell dak to import the new data (overriding the target suite)
        immutable heidiResult = postprocessHeidiFile (miWorkspace);
        auto ret = dak.setSuiteToBritneyResult (toSuite.name, heidiResult);

        // add the results to our database
        ret = updateDatabase (miWorkspace, fromSuite, toSuite) && ret;
        return ret;
    }

    bool runMigration (string fromSuite, string toSuite)
    {
        bool done = false;
        bool ret = true;

        foreach (ref mentry; spearsConf.migrations) {
            if ((mentry.sourceSuite == fromSuite) && (mentry.targetSuite == toSuite)) {
                auto scRes = suitesFromConfigEntry (mentry);
                if (scRes.error)
                    continue;
                done = true;
                if (!runMigrationInternal (scRes.from, scRes.to))
                    ret = false;
            }
        }

        if (!done) {
            logError ("Unable to find migration setup for '%s -> %s'", fromSuite, toSuite);
            return false;
        }

        return ret;
    }

    bool runMigration ()
    {
        bool ret = true;
        foreach (ref mentry; spearsConf.migrations) {
            auto scRes = suitesFromConfigEntry (mentry);
            if (scRes.error)
                continue;

            if (!runMigrationInternal (scRes.from, scRes.to))
                ret = false;
        }

        return ret;
    }

}
