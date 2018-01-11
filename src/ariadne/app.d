/*
 * Copyright (C) 2017-2018 Matthias Klumpp <matthias@tenstral.net>
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

import std.stdio;
import std.getopt;
import std.string : format;
import core.stdc.stdlib : exit;

import laniakea.localconfig;
import laniakea.logging;

import ariadne.buildscheduler : scheduleBuilds;


private immutable helpText =
"Usage:
  ariadne <subcommand> [OPTION...] - Automatically schedule package builds.

Laniakea module for planning package builds and various other actions related
to them.

Help Options:
  -h, --help       Show help options

Application Options:
  --version        Show the program version.
  --verbose        Show extra debugging information.
  --force          Force action.";

void main (string[] args)
{
    bool verbose;
    bool showHelp;
    bool showVersion;
    bool forceAction;

    // parse command-line options
    try {
        getopt (args,
            "help|h", &showHelp,
            "verbose", &verbose,
            "version", &showVersion,
            "force", &forceAction);
    } catch (Exception e) {
        writeln ("Unable to parse parameters: ", e.msg);
        exit (1);
    }

    if (showHelp) {
        writeln (helpText);
        return;
    }

    if (showVersion) {
        writeln ("Version: ", laniakea.localconfig.laniakeaVersion);
        return;
    }

    if (args.length < 2) {
        writeln ("No subcommand specified!");
        return;
    }

    auto conf = LocalConfig.get;
    try {
        conf.load (LkModule.ARIADNE);
    } catch (Exception e) {
        writefln ("Unable to load configuration: %s", e.msg);
        exit (4);
    }

    // globally enable verbose mode, if requested
    if (verbose) {
        laniakea.logging.setVerboseLog (true);
    }

    immutable command = args[1];
    if (command == "run") {
        if (!scheduleBuilds ())
            exit (1);
    } else {
        writeln ("Command ", command, " is unknown.");
        exit (2);
    }
}
