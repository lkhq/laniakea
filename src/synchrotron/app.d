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

import std.stdio;
import std.getopt;
import std.string : format;
import core.stdc.stdlib : exit;

import laniakea.config;
import laniakea.logging;

import synchrotron.syncengine;

private immutable helpText =
"Usage:
  synchrotron <subcommand> [OPTION...] - Sync packages.

Laniakea module for synchronizing packages with the source distribution.

Subcommands:
  sync SUITE SECTION PKGNAME - Process new metadata for the given distribution suite.
  autosync                   - Sync all packages which can be synced and process task queues.

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
        writeln ("Version: ", laniakea.config.laniakeaVersion);
        return;
    }

    if (args.length < 2) {
        writeln ("No subcommand specified!");
        return;
    }

    auto conf = BaseConfig.get ();
    try {
        conf.load ();
    } catch (Exception e) {
        writefln ("Unable to load configuration: %s", e.msg);
        exit (4);
    }

    // globally enable verbose mode, if requested
    if (verbose) {
        laniakea.logging.setVerbose (true);
    }

    auto engine = new SyncEngine ();
    immutable command = args[1];
    switch (command) {
        case "sync":
            if (args.length < 5) {
                writeln ("Invalid number of parameters: You need to specify a source section and package name.");
                exit (1);
            }

            // "default" is an alias for the defaulr sync source suite
            if (args[2] != "default")
                engine.setSourceSuite (args[2]);
            immutable ret = engine.syncPackages (args[3], args[4..$]);
            if (!ret)
                exit (2);
            break;
        case "autosync":
            immutable ret = engine.autosync ();
            if (!ret)
                exit (2);
            break;
        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
            break;
    }
}
