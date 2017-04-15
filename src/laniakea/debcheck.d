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

module laniakea.debcheck;
@safe:

import std.stdio;
import std.string;
import std.array : appender;
import std.conv : to;
import std.path : buildPath;

import laniakea.db;
import laniakea.localconfig;
import laniakea.pkgitems;
import laniakea.repository;

class Debcheck
{

    private {
        struct DoseResult
        {
            bool success;
            string data;
        }

        Database db;
        Repository repo;
    }

    this ()
    {
        db = Database.get;

        auto conf = LocalConfig.get;
        auto baseConfig = db.getBaseConfig;

        repo = new Repository (conf.archive.rootPath,
                                baseConfig.projectName);
        repo.setTrusted (true);
    }

    private DoseResult executeDose (const string dose_exe, const string[] args) @system
    {
        import std.process;

        string getOutput (File f)
        {
            char[1024] buf;
            auto output = appender!string;
            while (!f.eof) {
                auto res = f.rawRead (buf);
                output ~= res;
            }
            return output.data;
        }

        auto doseArgs = [dose_exe] ~ args;
        auto cmd = pipeProcess (doseArgs);

        if (wait (cmd.pid) != 0) {
            return DoseResult (false, getOutput (cmd.stdout) ~ "\n" ~ getOutput (cmd.stderr));
        }

        return DoseResult (true, getOutput (cmd.stdout));
    }

    private string getBuildDepCheckYaml (DistroSuite suite)
    {
        auto collIssues = db.getCollection! (LkModule.DEBCHECK, "issues");

        foreach (ref component; suite.components) {
            immutable indexFname = repo.getIndexFile (suite.name, buildPath (component, "source", "Sources.xz"));
        }

        return null;
    }
}
