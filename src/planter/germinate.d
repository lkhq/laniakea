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

module planter.germinate;

import std.stdio : File;
import std.process;
import std.array : appender, join;
import std.algorithm : map;
import std.string : format, toLower;
import std.path : buildPath;
static import std.file;

import laniakea.db;
import laniakea.logging;
import laniakea.localconfig;
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

    Database db;
    PlanterConfig planterConf;
    BaseConfig baseConf;
    LocalConfig localConf;

public:

    this ()
    {
        // default to system germinator (usually /usr/bin/germinate)
        germinateExe = "germinate";

        db = Database.get;
        planterConf = db.getPlanterConfig;
        baseConf = db.getBaseConfig;

        localConf = LocalConfig.get;
        immutable workspace = buildPath (localConf.workspace, "planter");
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
        if (!std.file.exists (buildPath (metaSrcDir, ".git"))) {
            std.file.mkdirRecurse (metaSrcDir);
            git.clone (planterConf.metaPackageGitSourceUrl);
        } else {
            git.pull ();
        }
    }

    bool run ()
    in { assert (db.getSuite (baseConf.archive.develSuite).architectures.length > 0); }
    body
    {
        immutable devSuiteName = baseConf.archive.develSuite;

        // update the seed (contained in the metapackage repository)
        updateMetapackage ();

         // NOTE: We make a hardcoded assumption on where the seed is located.
         // Since germinate expects it there currently, this isn't an issue today,
         // but could become one in future.
        immutable seedSrcDir = buildPath(metaSrcDir, "seed");

        // create target directory
        auto resultsDir = buildPath (resultsBaseDir, "%s.%s".format (baseConf.projectName.toLower, devSuiteName));
        std.file.mkdirRecurse (resultsDir);

        auto develSuite = db.getSuite (baseConf.archive.develSuite);

        // prepare parameters
        auto geArgs = ["-S", "file://" ~ seedSrcDir, // seed source
                       "-s", devSuiteName, // suite name
                       "-d", devSuiteName, // suite / dist name
                       "-m", "file://" ~ localConf.archive.rootPath, // mirror
                       "-c", develSuite.components.map!(c => c.name).join (" "), // components to check
                       "-a", develSuite.architectures[0]];
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
