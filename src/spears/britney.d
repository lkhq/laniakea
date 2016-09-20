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

import std.stdio : File;
import std.process;
import std.array : appender;
import std.path : baseName, buildPath;
static import std.file;

import laniakea.logging;
import laniakea.config;
import laniakea.git;

private immutable britneyGitRepository = "https://anonscm.debian.org/git/mirror/britney2.git";

/**
 * Interface to Debian's Archive Migrator (Britney2)
 */
class Britney
{

private:

    struct BritneyResult
    {
        bool success;
        string data;
    }

    string britneyExe;
    string britneyDir;

public:

    this ()
    {
        britneyDir = buildPath (BaseConfig.get ().workspace, "dist", "britney2");
        britneyExe = buildPath (britneyDir, "britney.py");
    }

    private BritneyResult runBritney (const string command, const string[] args)
    {
        string getOutput (File f)
        {
            char[] buf;
            auto output = appender!string;
            while (f.readln (buf)) {
                output ~= buf;
            }
            return output.data;
        }

        auto brArgs = [britneyExe] ~ command ~ args;
        auto brCmd = pipeProcess (brArgs);

        if (wait (brCmd.pid) != 0) {
            return BritneyResult (false, getOutput (brCmd.stdout) ~ "\n" ~ getOutput (brCmd.stderr));
        }

        return BritneyResult (true, getOutput (brCmd.stdout));
    }

    void updateDist ()
    {
        auto git = new Git;
        git.repository = britneyDir;
        if (!std.file.exists (britneyDir)) {
            std.file.mkdirRecurse (britneyDir);
            git.clone (britneyGitRepository);
        } else {
            git.pull ();
        }
    }
}
