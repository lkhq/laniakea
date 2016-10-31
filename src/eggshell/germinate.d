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
import std.array : appender, join;
import std.string : format;
import std.path : baseName, buildPath, dirName;
static import std.file;

import laniakea.logging;
import laniakea.config;
import laniakea.git;

/**
 * Interface to the Germinator
 */
class Germinate
{

private:

    struct GerminateResult
    {
        bool success;
        string data;
    }

    string germinateExe;
    string metaSrcDir;
    string resultsBaseDir;

    BaseConfig conf;

public:

    this ()
    {
        // default to system germinator (usually /usr/bin/germinate)
        germinateExe = "germinate";

        conf = BaseConfig.get ();

        immutable workspace = buildPath (conf.workspace, "eggshell");
        std.file.mkdirRecurse (workspace);

        // meta package / seed source directory
        metaSrcDir = buildPath (workspace, "meta");

        // output dir
        resultsBaseDir = buildPath (workspace, "results");
    }

    private GerminateResult runGerminateCmd (const string workDir, const string[] args)
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

        auto geArgs = [germinateExe] ~ args;
        auto geCmd = pipeProcess (geArgs,
                                  cast(Redirect) 7,
                                  cast(const(string[string])) null, // env
                                  cast(Config) null, // config
                                  workDir);

        bool running;
        auto stdoutText = appender!string;
        do {
            auto ge = tryWait (geCmd.pid);
            running = !ge.terminated;
            char[512] buf;
            if (!geCmd.stdout.eof) {
                auto res = geCmd.stdout.rawRead (buf);
                stdoutText ~= res;
                logVerbose (res);
            }
        } while (running);

        if (geCmd.pid.wait != 0) {
            return GerminateResult (false, stdoutText.data ~ "\n" ~ getOutput (geCmd.stderr));
        }

        return GerminateResult (true, stdoutText.data);
    }

    void updateMetapackage ()
    {
        auto git = new Git;
        git.repository = metaSrcDir;
        if (!std.file.exists (metaSrcDir)) {
            std.file.mkdirRecurse (metaSrcDir);
            git.clone (conf.eggshell.metaPackageGitSourceUrl);
        } else {
            git.pull ();
        }
    }

    bool run ()
    {
        immutable devSuiteName = conf.archive.develSuite.name;

        // update the seed (contained in the metapackage repository)
        updateMetapackage ();

         // NOTE: We make a hardcoded assumption on where the seed is located.
         // Since germinate expects it there currently, this isn't an issue today,
         // but could become one in future.
        immutable seedSrcDir = buildPath(metaSrcDir, "seed");

        // create target directory
        auto resultsDir = buildPath (resultsBaseDir, "%s.%s".format (conf.projectName, devSuiteName));
        std.file.mkdirRecurse (resultsDir);

        // prepare parameters
        auto geArgs = ["-S", "file://" ~ seedSrcDir,
                       "-s", devSuiteName,
                       "-d", devSuiteName,
                       "-m", "file://" ~ conf.archive.rootPath,
                       "-c", conf.archive.develSuite.components.join (" ")];
        // NOTE: Maybe we want to limit the seed to only stuff in the primary (main) component?

        // execute germinator
        auto res = runGerminateCmd (resultsDir, geArgs);

        if (!res.success) {
            logError ("Germinate run has failed: %s", res.data);
            return false;
        }

        return true;
    }

}
