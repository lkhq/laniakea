/*
 * Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
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
import std.string : format;
import core.stdc.stdlib : exit;

import laniakea.localconfig;
import laniakea.logging;
import laniakea.cmdargs;

import admin.admintool;
import admin.baseadmin;
import admin.planteradmin;
import admin.spearsadmin;
import admin.syncadmin;
import admin.isotopeadmin;

private immutable progname    = "lk-admin";
private immutable helpSummary = "Run CLI admin actions.";

private immutable helpDescription = "Laniakea CLI administration.";

void main (string[] args)
{
    bool verbose;
    bool showHelp;
    bool showVersion;

    // parse command-line options
    GetoptResult goRes;
    try {
        goRes = getopt (args,
            std.getopt.config.passThrough,
            "help|h",  "Show helpful information.", &showHelp,
            "verbose", "Show extra debugging information.", &verbose,
            "version", "Show the program version.", &showVersion);
    } catch (Exception e) {
        writeln ("Unable to parse parameters: ", e.msg);
        exit (1);
    }

    auto conf = LocalConfig.get;
    try {
        conf.load (LkModule.ADMINCLI);
    } catch (Exception e) {
        writefln ("Unable to load configuration: %s", e.msg);
        exit (4);
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

    // create a list of subcommand information
    SubcommandInfo[] subcommands;
    subcommands ~= SubcommandInfo ("init-db", "Initialize the database.");
    subcommands ~= SubcommandInfo ("init", "Configure all modules.");
    subcommands ~= SubcommandInfo ("config-set", "Set a global configuration option by its key.");
    subcommands ~= SubcommandInfo ("random-name", "Generate a random memorizable string.");
    foreach (ref tool; tools) {
        subcommands ~= tool.toolInfo;
    }

    if (showHelp && args.length == 1) {
        printHelpText (progname,
                       helpSummary,
                       helpDescription,
                       subcommands,
                       goRes.options);
        return;
    }

    if (showVersion) {
        printLaniakeaVersion ();
        return;
    }

    if (args.length < 2) {
        writeln ("No subcommand specified!");
        return;
    }

    // globally enable verbose mode, if requested
    if (verbose) {
        laniakea.logging.setVerboseLog (true);
    }

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
                if (command == tool.toolInfo.name) {
                    if (args.length < 3) {
                        writeln ("Invalid number of parameters: You need to specify an action.");
                        writeln ();
                        tool.printHelp (progname);
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
