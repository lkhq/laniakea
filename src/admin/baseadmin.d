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

module admin.baseadmin;

import std.stdio : writeln;
import std.string : format;

import laniakea.db;
import admin.admintool;


/**
 * Perform various basic administrative actions.
 */
final class BaseAdmin : AdminTool
{
    @property
    override string toolId ()
    {
        return "base";
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
                baseDumpConfig ();
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
        writeHeader ("Configuring base settings for Laniakea");

        BaseConfig bconf;

        writeQS ("Name of this project");
        bconf.projectName = readString ();

        bool addSuite = true;
        while (addSuite) {
            import std.algorithm : canFind;

            DistroSuite suite;
            writeQS ("Adding a new suite. Please set a name");
            suite.name = readString ();

            writeQS ("List of components for suite '%s'".format (suite.name));
            auto componentsList = readList ();
            auto addMainDep = false;
            addMainDep = componentsList.canFind ("main");
            foreach (ref cname; componentsList) {
                DistroComponent c;
                c.name = cname;
                if (addMainDep && c.name != "main")
                    c.dependencies ~= "main";
                suite.components ~= c;
            }

            writeQS ("List of architectures for suite '%s'".format (suite.name));
            suite.architectures = readList ();

            bconf.suites ~= suite;

            writeQB ("Add another suite?");
            addSuite = readBool ();
        }

        writeQS ("Name of the 'incoming' suite which new packages are usually uploaded to");
        bconf.archive.incomingSuite = readString ();

        writeQS ("Name of the 'development' suite which is rolling or will become a final release");
        bconf.archive.develSuite = readString ();

        writeQS ("Distribution version tag (commonly found in package versions, e.g. 'tanglu' for OS 'Tanglu' with versions like '1.0-0tanglu1'");
        bconf.archive.distroTag = readString ();

        // update database with new configuration
        db.update (bconf);

        return true;
    }

    void baseDumpConfig ()
    {
        writeln (db.getBaseConfig ().serializeToPrettyJson);
    }
}
