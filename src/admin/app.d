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
import admin.baseadmin;
import admin.planteradmin;
import admin.spearsadmin;
import admin.syncadmin;
import admin.isotopeadmin;

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
            std.getopt.config.passThrough,
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
        laniakea.logging.setVerboseLog (true);
    }

    // list of tools that we have - needs to be initialized after
    // the global local configuration has been set up, so the database
    // connection can be initialized.
    AdminTool[] tools = [
        new BaseAdmin,
        new PlanterAdmin,
        new SpearsAdmin,
        new SyncAdmin,
        new IsotopeAdmin
    ];

    immutable command = args[1];
    switch (command) {
        case "init-db":
            import laniakea.db.database : Database;
            import laniakea.db.maintenance : initializeDatabase;
            auto db = Database.get;
            db.initializeDatabase ();
            break;
        case "init":
            foreach (ref tool; tools) {
                if (!tool.initDb ())
                    exit (2);
            }
            break;
        case "config-set":
            if (args.length < 4) {
                writeln ("Invalid number of parameters: You need to specify a module and an update command.");
                exit (1);
            }
            if (!setLaniakeaDbConfValue (args[2], args[3]))
                exit (2);
            break;
        case "random-name":
            import laniakea.utils.namegen : generateName, RandomNameStyle;
            import std.conv : to;

            bool animals = false;
            try {
                getopt (args,
                    "animal", &animals);
            } catch (Exception e) {
                writeln ("Unable to parse parameters: ", e.msg);
                exit (1);
            }

            int amount = 1;
            if (args.length >= 3)
                amount = args[2].to!int;
            for (int i = 0; i < amount; i++)
                writeln (generateName (animals? RandomNameStyle.ANIMAL : RandomNameStyle.RANDOM));
            break;
        default:
            foreach (ref tool; tools) {
                if (command == tool.toolId) {
                    if (args.length < 3) {
                        writeln ("Invalid number of parameters: You need to specify an action.");
                        exit (1);
                    }

                    exit (tool.run (args[2..$]));
                }
            }

            // if we get here, we have no tool that can handle this command
            writeln ("The command '%s' is unknown.".format (command));
            exit (1);
            break;
    }
}
