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

static import yaml;

import laniakea.logging;
import laniakea.db.schema.spears;

/**
 * Read the excuses.yml Britney output file and create SpearsExcuse structs to
 * be added to the database.
 */
class ExcusesFile
{

private:
    yaml.Node yroot;

    string sourceSuite;
    string targetSuite;

public:

    this (string fname, string source, string target)
    {
        yroot = yaml.Loader (fname).load ();

        sourceSuite = source;
        targetSuite = target;
    }

    private auto toStringArray (yaml.Node node)
    {
        string[] res;
        res.reserve (node.length);
        foreach (ref yaml.Node n; node)
            res ~= n.as!string;

        return res;
    }

    SpearsExcuse[string] getExcuses () @trusted
    {
        SpearsExcuse[string] res;

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

            auto ypolicy = yentry["policy_info"];
            excuse.age.currentAge = ypolicy["age"]["current-age"].as!uint;
            excuse.age.requiredAge = ypolicy["age"]["age-requirement"].as!uint;

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

            res[excuse.sourcePackage ~ "/" ~ excuse.newVersion] = excuse;
        }

        return res;
    }
}
