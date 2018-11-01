/*
 * Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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

module admin.ariadneadmin;

import std.stdio : writeln;
import std.string : format;
import std.array : empty;

import laniakea.db;
import admin.admintool;


/**
 * Ariadne administration.
 */
final class AriadneAdmin : AdminTool
{
    @property
    override SubcommandInfo toolInfo ()
    {
        return SubcommandInfo ("ariadne", "Configure the Ariadne package builder module.");
    }

    override
    int run (string[] args)
    {
        immutable command = args[0];

        bool ret = true;
        switch (command) {
            case "init":
                ret = initDb ();
                break;
            case "dump":
                ariadneDumpConfig ();
                break;
            default:
                writeln ("The command '%s' is unknown.".format (command));
                return 1;
        }

        if (!ret)
            return 2;
        return 0;
    }

    override
    void printHelp (string progname)
    {
        printHelpText (progname, toolInfo.summary, "???", [], [], toolInfo.name);
    }

    override
    bool initDb ()
    {
        writeHeader ("Configuring settings for Ariadne (package building)");

        AriadneConfig aconf;

        do {
            writeQS ("Architecture affinity for arch:all / arch-indep packages");
            aconf.indepArchAffinity = readString ();
            if (aconf.indepArchAffinity == "all") {
                writeln ("Architecture affinity for arch:all can not be arch:all as well.");
                aconf.indepArchAffinity = null;
            }
        } while (aconf.indepArchAffinity.empty);

        // update database
        db.update (aconf);

        return true;
    }

    void ariadneDumpConfig ()
    {
        writeln (db.getAriadneConfig ().serializeToPrettyJson);
    }
}
