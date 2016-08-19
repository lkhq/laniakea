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
import std.process;
import std.array : appender, join;
import std.path : baseName;
import std.algorithm : map;

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
        dakExecutable = "dak";
    }

    private DakResult executeDak (const string command, const string[] args)
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

        auto dakArgs = [dakExecutable] ~ command ~ args;
        auto dakCmd = pipeProcess (dakArgs);

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
            logError ("Unable to import package '%s': %s", fnames.join (" "), res.data);
            return false;
        }

        logInfo ("Imported package '%s' to '%s/%s'.", map!(baseName) (fnames).join (" "), suite, component);
        return true;
    }

}
