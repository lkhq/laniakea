/*
 * Copyright (C) 2016-2017 Matthias Klumpp <matthias@tenstral.net>
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

module spears.britney;

import std.stdio : File;
import std.process;
import std.array : appender;
import std.string : format;
import std.path : baseName, buildPath, dirName;
static import std.file;

import laniakea.logging;
import laniakea.localconfig;
import laniakea.git;

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
    string britneyGitRepository;

public:

    this ()
    {
        import laniakea.utils : readJsonFile;

        britneyDir = buildPath (LocalConfig.get.workspace, "dist", "britney2");
        britneyExe = buildPath (britneyDir, "britney.py");

        // fetch the location of the Brithey git repository from static data
        auto jroot = readJsonFile (getDataFile ("3rd-party.json"));
        if ("Spears" !in jroot)
            throw new Exception ("Unable to find Git URL for britney in 3rd-party.json static data.");
        const spearsJ = jroot["Spears"];
        britneyGitRepository = spearsJ["britneyGitRepository"].to!string;
    }

    private BritneyResult runBritney (const string workDir, const string[] args)
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

        auto brArgs = [britneyExe] ~ args;
        auto brCmd = pipeProcess (brArgs,
                                  cast(Redirect) 7,
                                  cast(const(string[string])) null, // env
                                  cast(Config) null, // config
                                  workDir);

        bool running;
        auto stdoutText = appender!string;
        do {
            auto br = tryWait (brCmd.pid);
            running = !br.terminated;

            char[512] buf;
            if (!brCmd.stdout.eof) {
                auto res = brCmd.stdout.rawRead (buf);
                stdoutText ~= res;
                logVerbose (res);
            }
        } while (running);

        if (wait (brCmd.pid) != 0) {
            return BritneyResult (false, stdoutText.data ~ "\n" ~ getOutput (brCmd.stderr));
        }

        return BritneyResult (true, stdoutText.data);
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

    string run (string configFile)
    {
        auto res = runBritney (configFile.dirName, ["-c", configFile, "-v"]);
        if (!res.success)
            throw new Exception ("Britney run failed: %s".format (res.data));

        return res.data;
    }

}
