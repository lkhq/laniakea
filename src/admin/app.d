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

import std.stdio;
import std.getopt;
import std.string : format;
import core.stdc.stdlib : exit;

import laniakea.localconfig;
import laniakea.logging;

import admin.admintool;

private immutable helpText =
"Usage:
  lk-admin <subcommand> [OPTION...] - Run CLI admin actions.

Laniakea CLI administration.

Subcommands:
  TODO
Help Options:
  -h, --help       Show help options

Application Options:
  --version        Show the program version.
  --verbose        Show extra debugging information.";

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
            "version", &showVersion);
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
        conf.load (LkModule.ADMINCLI);
    } catch (Exception e) {
        writefln ("Unable to load configuration: %s", e.msg);
        exit (4);
    }

    // globally enable verbose mode, if requested
    if (verbose) {
        laniakea.logging.setVerbose (true);
    }

    auto tool = new AdminTool ();
    immutable command = args[1];
    switch (command) {
        case "init":
            if (!tool.baseInit ())
                exit (2);
            if (!tool.synchrotronInit ())
                exit (2);
            if (!tool.spearsInit ())
                exit (2);
            break;
        case "config-set":
            if (args.length < 4) {
                writeln ("Invalid number of parameters: You need to specify a module and an update command.");
                exit (1);
            }
            if (!tool.setConfValue (args[2], args[3]))
                exit (2);
            break;
        case "base":
            processBaseCommands (tool, args);
            break;
        case "synchrotron":
            processSynchrotronCommands (tool, args);
            break;
        case "spears":
            processSpearsCommands (tool, args);
            break;
        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
            break;
    }
}

private void processBaseCommands (AdminTool tool, string[] args)
{
    if (args.length < 3) {
        writeln ("Invalid number of parameters: You need to specify an action.");
        exit (1);
    }
    immutable command = args[2];

    bool ret = true;
    switch (command) {
        case "init":
            ret = tool.baseInit ();
            break;
        case "dump":
            tool.baseDumpConfig ();
            break;
        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
        break;
    }
    if (!ret)
        exit (2);
}

private void processSynchrotronCommands (AdminTool tool, string[] args)
{
    if (args.length < 3) {
        writeln ("Invalid number of parameters: You need to specify an action.");
        exit (1);
    }
    immutable command = args[2];

    bool ret = true;
    switch (command) {
        case "init":
            ret = tool.synchrotronInit ();
            break;
        case "dump":
            tool.synchrotronDumpConfig ();
            break;
        case "blacklist-add":
            if (args.length < 5) {
                writeln ("Invalid number of parameters: You need to specify a package to add and a reason to ignore it.");
                exit (1);
            }
            tool.synchrotronBlacklistAdd (args[3], args[4]);
            break;
        case "blacklist-remove":
            if (args.length < 4) {
                writeln ("Invalid number of parameters: You need to specify a package to remove.");
                exit (1);
            }
            tool.synchrotronBlacklistRemove (args[3]);
            break;
        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
        break;
    }

    if (!ret)
        exit (2);
}

private void processSpearsCommands (AdminTool tool, string[] args)
{
    if (args.length < 3) {
        writeln ("Invalid number of parameters: You need to specify an action.");
        exit (1);
    }
    immutable command = args[2];

    bool ret = true;
    switch (command) {
        case "init":
            ret = tool.spearsInit ();
            break;
        case "dump":
            tool.spearsDumpConfig ();
            break;
        default:
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
        break;
    }
    if (!ret)
        exit (2);
}
