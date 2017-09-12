/*
 * Copyright (C) 2017 Matthias Klumpp <matthias@tenstral.net>
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

module admin.eggshelladmin;

import std.stdio : writeln;
import std.string : format;

import vibe.db.mongo.mongo;
import laniakea.db;
import admin.admintool;


/**
 * Eggshell administration.
 */
final class EggshellAdmin : AdminTool
{
    @property
    override string toolId ()
    {
        return "eggshell";
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
                eggshellDumpConfig ();
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
    bool initDb ()
    {
        writeHeader ("Configuring settings for Eggshell (metapackages / germinator)");

        EggshellConfig esconf;

        SpearsConfigEntry migration;
        writeQS ("Git pull URL for the germinate metapackage sources");
        esconf.metaPackageGitSourceUrl = readString ();

        // update database
        db.update (esconf);

        return true;
    }

    void eggshellDumpConfig ()
    {
        writeln (db.getEggshellConfig ().serializeToPrettyJson);
    }
}
