/*
 * Copyright (C) 2017 Matthias Klumpp <matthias@tenstral.net>
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

module spears.excuses;
@safe:

import std.array : appender;
import std.algorithm : canFind;
static import yaml;

import laniakea.logging;
import laniakea.db.schema.spears;

/**
 * Read the excuses.yml Britney output file as well as the Britney logfile
 * and create SpearsExcuse structs to be added to the database from their data.
 */
class ExcusesFile
{

private:
    yaml.Node yroot;

    string sourceSuite;
    string targetSuite;

    string logContent;

public:

    this (string excusesFname, string logFname, string source, string target) @trusted
    {
        import std.stdio;

        sourceSuite = source;
        targetSuite = target;

        yroot = yaml.Loader (excusesFname).load ();

        auto f = File (logFname, "r");
        auto lData = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            lData ~= line;
        logContent = lData.data;
    }

    private auto toStringArray (yaml.Node node)
    {
        string[] res;
        res.reserve (node.length);
        foreach (ref yaml.Node n; node)
            res ~= n.as!string;

        return res;
    }

    /**
     * Generate a dictionary of packageName -> logExcerpt from
     * the logfile.
     */
    private string[string] processLogData ()
    {
        import std.string;

        string[string] res;
        string[] currentPackages;
        bool autoHinter = false;
        foreach (line; logContent.splitLines) {
            // stop adding hinter information if we leave a block
            if (line.empty) {
                autoHinter = false;
                currentPackages = [];
                continue;
            }

            // simple migrations
            if (line.startsWith ("trying:"))
                currentPackages = [line[7..$].strip];

            // autohinter action
            if (line.startsWith ("Trying easy from autohinter:")) {
                autoHinter = true;
                auto pkgsLine = line[28..$].strip;
                foreach (ref pkgid; pkgsLine.split (" ")) {
                    auto parts = pkgid.split ("/");
                    currentPackages ~= parts[0];
                }
            }

            // ignore uninteresting entries
            if (currentPackages.empty)
                continue;
            foreach (ref pkg; currentPackages)
                res[pkg] ~= line ~ "\n";
        }

        return res;
    }

    SpearsExcuse[string] getExcuses ()
    {
        SpearsExcuse[string] res;

        // get log data
        auto logInfo = processLogData ();

        auto ysrc = yroot["sources"];
        foreach(yaml.Node yentry; ysrc) {
            SpearsExcuse excuse;

            excuse.sourceSuite = sourceSuite;
            excuse.targetSuite = targetSuite;

            excuse.sourcePackage = yentry["source"].as!string;
            excuse.maintainer = yentry["maintainer"].as!string;
            excuse.isCandidate = yentry["is-candidate"].as!bool;

            excuse.newVersion = yentry["new-version"].as!string;
            excuse.oldVersion = yentry["old-version"].as!string;

            if (yentry.containsKey ("policy_info")) {
                auto ypolicy = yentry["policy_info"];
                excuse.age.currentAge = ypolicy["age"]["current-age"].as!uint;
                excuse.age.requiredAge = ypolicy["age"]["age-requirement"].as!uint;
            }

            if (yentry.containsKey ("missing-builds")) {
                auto ybuilds = yentry["missing-builds"];
                excuse.missingBuilds.primaryArchs = toStringArray (ybuilds["on-architectures"]);
                excuse.missingBuilds.secondaryArchs = toStringArray (ybuilds["on-unimportant-architectures"]);
            }

            if (yentry.containsKey ("old-binaries")) {
                foreach (yaml.Node yver, yaml.Node ybins; yentry["old-binaries"]) {
                    SpearsOldBinaries oldBin;

                    oldBin.pkgVersion = yver.as!string;
                    oldBin.binaries   = toStringArray (ybins);
                    excuse.oldBinaries ~= oldBin;
                }
            }

            if (yentry.containsKey ("dependencies")) {
                auto ydeps = yentry["dependencies"];
                if (ydeps.containsKey ("migrate-after")) {
                    excuse.reason.migrateAfter = toStringArray (ydeps["migrate-after"]);
                }
                if (ydeps.containsKey ("blocked-by")) {
                    excuse.reason.blockedBy = toStringArray (ydeps["blocked-by"]);
                }
            }

            // other plaintext excuses
            if (yentry.containsKey ("excuses")) {
                auto yn = yentry["excuses"];

                excuse.reason.other.reserve (yn.length);
                foreach (ref yaml.Node n; yn) {
                    auto s = n.as!string;
                    if ((!s.canFind("Cannot be tested by piuparts")) && (!s.canFind("but ignoring cruft, so nevermind")))
                        excuse.reason.other ~= s;
                }
            }

            // add log information
            auto logInfoP = excuse.sourcePackage in logInfo;
            if (logInfoP !is null) {
                excuse.reason.logExcerpt = (*logInfoP);
            }

            res[excuse.sourcePackage ~ "/" ~ excuse.newVersion] = excuse;
        }

        return res;
    }
}
