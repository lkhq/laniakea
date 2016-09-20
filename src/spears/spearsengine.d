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
import std.string : format;
import std.algorithm : canFind;
import std.path : buildPath;
import std.array : appender;
import std.typecons : Tuple;
static import std.file;

import laniakea.repository.dak;
import laniakea.pkgitems;
import laniakea.config;
import laniakea.logging;

import spears.britneyconfig;
import spears.britney;

/**
 * Run package migrations using Britney and manage its configurations.
 */
class SpearsEngine
{

private:

    Britney britney;
    BaseConfig conf;

public:

    this ()
    {
        britney = new Britney ();
        conf = BaseConfig.get ();
    }

    alias SuiteCheckResult = Tuple!(DistroSuite, "from", DistroSuite, "to", bool, "error");
    private SuiteCheckResult suitesFromConfigEntry (SpearsConfigEntry centry)
    {
        SuiteCheckResult res;
        res.error = false;

        auto maybeSuite = conf.getSuite (centry.fromSuite);
        if (maybeSuite.isNull) {
            logError ("Migration source suite '%s' does not exist. Can not create configuration.", centry.fromSuite);
            res.error = true;
            return res;
        }
        res.from = maybeSuite.get ();

        maybeSuite = conf.getSuite (centry.toSuite);
        if (maybeSuite.isNull) {
            logError ("Migration target suite '%s' does not exist. Can not create configuration.", centry.toSuite);
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

    bool updateConfig ()
    {
        immutable workspace = buildPath (conf.workspace, "spears");
        std.file.mkdirRecurse (workspace);

        logInfo ("Updating configuration");
        immutable archiveRootPath = conf.archive.rootPath;
        foreach (ref mentry; conf.spears) {
            auto scRes = suitesFromConfigEntry (mentry);
            if (scRes.error)
                continue;
            auto fromSuite = scRes.from;
            auto toSuite = scRes.to;

            logInfo ("Refreshing Britney config for '%s -> %s'", fromSuite.name, toSuite.name);
            immutable miWorkspace = buildPath (workspace, "%s-to-%s".format (fromSuite.name, toSuite.name));
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

    bool runMigration (string fromSuite, string toSuite)
    {
        return true;
    }

    bool runMigration ()
    {
        return true;
    }

}
