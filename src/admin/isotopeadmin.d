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

module admin.isotopeadmin;

import std.stdio : writeln;
import std.string : format;

import laniakea.db;
import admin.admintool;


/**
 * Isotope administration.
 */
final class IsotopeAdmin : AdminTool
{
    @property
    override SubcommandInfo toolInfo ()
    {
        return SubcommandInfo ("isotope", "Configure the disk image build module.");
    }

    override
    int run (string[] args)
    {
        immutable command = args[0];

        bool ret = true;
        switch (command) {
            case "dump":
                dumpRecipes ();
                break;
            case "add-recipe":
                addRecipe ();
                break;
            case "trigger-build":
                if (args.length < 2) {
                    writeln ("Invalid number of parameters: You need to specify a recipe name (usually {distro}-{suite}-{flavor}).");
                    return 1;
                }
                ret = triggerBuild (args[1]);
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

    void dumpRecipes ()
    {
        auto conn = db.getConnection;
        foreach (ref rawRecipe; conn.getBuildRecipes (0)) {
            writeln (rawRecipe.serializeToPrettyJson);
            writeln ();
        }
    }

    void addRecipe ()
    {
        import std.uni : toLower;
        import std.typecons : tuple;
        import std.uuid : randomUUID;

        writeHeader ("Add new ISO image build recipe");
        ImageBuildRecipe recipe;
        recipe.uuid = randomUUID ();

        writeQS ("Name of the distribution to build the image for");
        recipe.distribution = readString ();

        writeQS ("Name of the suite to build the image for");
        recipe.suite = readString ();

        writeQS ("Flavor to build");
        recipe.flavor = readString ();

        writeQL ("List of architectures to build for");
        recipe.architectures = readList ();

        writeQS ("Git repository URL containing the live-build configuration");
        recipe.liveBuildGit = readString ();

        writeQS ("Place to move the build result to (placeholders like %{DATE} are allowed)");
        recipe.resultMoveTo = readString ();

        // ensure we have a name
        recipe.name = "%s-%s-%s".format (recipe.distribution, recipe.suite, recipe.flavor).toLower;

        // add recipe to the database
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);
        conn.update (recipe);

        writeDone ("Created recipe with name: %s".format (recipe.name));
    }

    bool triggerBuild (string name)
    {
        import std.typecons : tuple;
        import vibe.data.json : serializeToJson;

        auto conn = db.getConnection;

        auto recipe = conn.getRecipeByName (name);
        if (recipe.isNull) {
            writeln ("No build recipe matching these parameters has been found.");
            return false;
        }

        foreach (ref arch; recipe.architectures) {
            Job isojob;
            isojob.architecture  = arch;
            conn.addJob (isojob,
                         LkModule.ISOTOPE,
                         JobKind.OS_IMAGE_BUILD,
                         recipe.uuid);
        }

        return true;
    }
}
