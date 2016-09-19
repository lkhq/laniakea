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

import std.array : empty, join;
import std.string : format, toUpper;
import std.path : buildPath;
import std.array : appender, Appender;
import std.conv : to;
static import std.file;

import laniakea.logging;
import laniakea.pkgitems;

/**
 * A Britney2 configuration file.
 */
class BritneyConfig
{

private:
    immutable string baseDir;

    Appender!(string[]) contents;

public:

    this (string britneyDir)
    {
        baseDir = britneyDir;
        contents = appender!(string[]);

        // add basic settings
        contents ~= "# Configuration file for Britney\n# This file is managed by Laniakea.Spears - DO NOT EDIT IT MANUALLY!\n";

        // output
        contents ~= "NONINST_STATUS      = output/target/non-installable-status";
        contents ~= "EXCUSES_OUTPUT      = output/target/excuses.html";
        contents ~= "EXCUSES_YAML_OUTPUT = output/target/excuses.yaml";
        contents ~= "UPGRADE_OUTPUT      = output/target/output.txt";
        contents ~= "HEIDI_OUTPUT        = output/target/HeidiResult";

        // external policy/constraints/faux-packages information that
        // (presumably) rarely changes.  Examples include "constraints".
        contents ~= "STATIC_INPUT_DIR = input/";
        contents ~= "HINTSDIR         = input/hints";

        // directory for input files that Britney will update herself
        // (e.g. aging information) or will need regular updates
        // (e.g. urgency information).
        contents ~= "STATE_DIR        = state/";

        // support for old libraries in testing (smooth update)
        // use ALL to enable smooth updates for all the sections
        //
        // naming a non-existent section will effectively disable new smooth
        // updates but still allow removals to occur
        contents ~=  "SMOOTH_UPDATES = libs oldlibs";
        contents ~=  "IGNORE_CRUFT   = 1";
    }

    void setArchivePaths (string fromPath, string toPath)
    {
        // paths for control files
        contents ~= "UNSTABLE = %s".format (fromPath);
        contents ~= "TESTING  = %s".format (toPath);

    }

    void setComponents (string[] components)
    {
        contents ~= "COMPONENTS = %s".format (components.join (", "));
    }

    void setArchitectures (string[] archs)
    {
        immutable archStr = archs.join (" ");

        // List of release architectures
        contents ~= "ARCHITECTURES = %s".format (archStr);

        // if you're not in this list, arch: all packages are allowed to break on you
        contents ~= "NOBREAKALL_ARCHES = %s".format (archStr);
    }

    void setDelays (uint[VersionPriority] delays)
    {
        foreach (ref prio, ref days; delays) {
            contents ~= "MINDAYS_%s = %s".format (prio.toString.toUpper, to!string (days));
        }

        contents ~= "DEFAULT_URGENCY   = medium";
    }

    void save ()
    {
        import std.stdio;

        // ensure essential directories exist
        std.file.mkdirRecurse (buildPath (baseDir, "output", "target"));
        std.file.mkdirRecurse (buildPath (baseDir, "input", "hints"));
        std.file.mkdirRecurse (buildPath (baseDir, "state"));

        // save configuration
        immutable confFname = buildPath (baseDir, "britney.conf");
        logDebug ("Saving Britney config to '%s'", confFname);

        auto f = File (confFname, "w");
        foreach (ref line; contents.data) {
            f.writeln (line);
        }
    }

}
