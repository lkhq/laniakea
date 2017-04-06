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

module laniakea.repository.dak;

import std.stdio : File;
import std.string : format;
import std.process;
import std.array : appender, join, empty;
import std.path : baseName;
import std.algorithm : map;
static import std.file;

import laniakea.logging;

/**
 * Interface to the Debian Archive Kit (DAK)
 */
class Dak
{

private:

    struct DakResult
    {
        bool success;
        string data;
    }

    string dakExecutable;

public:

    this ()
    {
        dakExecutable = "/usr/local/bin/dak";
        if (!std.file.exists (dakExecutable))
            dakExecutable = "dak";
    }

    @property
    string urgencyExportDir ()
    {
        // FIXME: Don't hardcode this!
        return "/srv/dak/export/urgencies/";
    }

    private DakResult executeDak (const string command, const string[] args, string stdinData = null)
    {
        string getOutput (File f)
        {
            char[512] buf;
            auto output = appender!string;
            while (!f.eof) {
                auto res = f.rawRead (buf);
                output ~= res;
            }
            return output.data;
        }

        auto dakArgs = [dakExecutable] ~ command ~ args;
        auto dakCmd = pipeProcess (dakArgs);

        if (stdinData !is null) {
            dakCmd.stdin.write (stdinData);
            dakCmd.stdin.flush ();
            dakCmd.stdin.close ();
        }

        if (wait (dakCmd.pid) != 0) {
            return DakResult (false, getOutput (dakCmd.stdout) ~ "\n" ~ getOutput (dakCmd.stderr));
        }

        return DakResult (true, getOutput (dakCmd.stdout));
    }

    bool importPackageFiles (const string suite, const string component, const string[] fnames,
                        bool ignoreSignature = false, bool addOverrides = false)
    {
        // run dak import command.
        auto args = appender!(string[]);
        if (ignoreSignature)
            args ~= "-s";
        if (addOverrides)
            args ~= "-a";
        args ~= suite;
        args ~= component;
        args ~= fnames;
        immutable res = executeDak ("import", args.data);

        if (!res.success) {
            logError ("Unable to import package files '%s': %s", fnames.join (" "), res.data);
            return false;
        }

        logInfo ("Imported '%s' to '%s/%s'.", map!(baseName) (fnames).join (" "), suite, component);
        return true;
    }

    /**
     * Import a Britney result (HeidiResult file) into the dak database.
     * This will *override* all existing package information in the target suite.
     * Use this command with great care!
     **/
    bool setSuiteToBritneyResult (string suiteName, string heidiFile)
    {
        import std.string : strip;

        // do some sanity checks
        if (!std.file.exists (heidiFile)) {
            logWarning ("Britney result not imported: File '%s' does not exist.", heidiFile);
            return false;
        }

        // an empty file might cause us to delete the whole repository contents.
        // this is a safeguard against that.
        immutable heidiData = std.file.readText (heidiFile).strip;
        if (heidiData.empty) {
            logWarning ("Stopped Britney result import: File '%s' is empty.", heidiFile);
            return false;
        }

        logInfo ("Importing britney result from %s", heidiFile);

        // run dak control-suite command.
        auto args = ["--set", suiteName, "--britney"];
        immutable res = executeDak ("control-suite", args, heidiData);

        if (!res.success)
            throw new Exception ("Unable apply Britney result to '%s': %s".format (suiteName, res.data));

        logInfo ("Updated packages in '%s' based on Britney result.", suiteName);
        return true;
    }

    /**
     * Check if a package can be removed without breaking reverse dependencies.
     **/
    bool packageIsRemovable (string packageName, string suiteName)
    {
        import std.algorithm : canFind;

        logDebug ("Testing package '%s' remove from '%s'", packageName, suiteName);

        // simulate package removal
        auto args = ["-R",
                     "-m", "'RID: Removed from Debian'",
                     "-C", "janitor@dak",
                     "-n",
                     "-s", suiteName,
                     packageName];
        immutable res = executeDak ("rm", args);

        if (!res.success)
            throw new Exception ("Unable to check if package '%s' is removable from '%s': %s".format (packageName, suiteName, res.data));

        return res.data.canFind ("No dependency problem found.");
    }

    /**
     * Remove a package from a specified suite.
     **/
    bool removePackage (string packageName, string suiteName)
    {
        import std.algorithm : canFind;

        logInfo ("Removing '%s' from '%s'", packageName, suiteName);

        // actually remove a package
        auto args = ["-m", "'RID: Removed from Debian'",
                     "-C", "janitor@dak",
                     "-s", suiteName,
                     packageName];
        immutable res = executeDak ("rm", args, "y\n");

        if (!res.success)
            throw new Exception ("Unable to remove package '%s' from '%s': %s".format (packageName, suiteName, res.data));

        return true;
    }

}
