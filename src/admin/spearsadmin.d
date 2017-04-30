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

module admin.spearsadmin;

import std.stdio : writeln, writefln;
import std.string : format;

import vibe.db.mongo.mongo;
import laniakea.db;
import laniakea.pkgitems;
import admin.admintool;


/**
 * Spears administration.
 */
final class SpearsAdmin : AdminTool
{
    @property
    override string toolId ()
    {
        return "spears";
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
                spearsDumpConfig ();
                break;
            case "add-hint":
                if (args.length < 5) {
                    writeln ("Invalid number of parameters: You need to specify a source-suite, a target-suite, a hint and a hint-reason.");
                    return 1;
                }
                spearsAddHint (args[1], args[2], args[3], args[4]);
                break;
            case "remove-hint":
                if (args.length < 4) {
                    writeln ("Invalid number of parameters: You need to specify a hint to remove.");
                    return 1;
                }
                spearsRemoveHint (args[1], args[2], args[3]);
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
        import std.traits;

        writeHeader ("Configuring settings for Spears (migrations)");

        SpearsConfig spconf;

        bool addMigration = true;
        while (addMigration) {
            SpearsConfigEntry migration;
            writeQS ("Migrate from suite (source name)");
            migration.sourceSuite = readString ();

            writeQS ("Migrate to suite (target name)");
            migration.targetSuite = readString ();

            foreach (immutable prio; [EnumMembers!VersionPriority]) {
                writeQI ("Delay for packages of priority '%s' in days".format (prio));
                immutable delay = readInt ();
                migration.delays[prio] = delay;
            }

            spconf.migrations ~= migration;

            writeQB ("Add another migration task?");
            addMigration = readBool ();
        }

        auto coll = db.collConfig;
        spconf.id = BsonObjectID.generate ();
        coll.remove (["module": LkModule.SPEARS, "kind": spconf.kind]);
        coll.update (["module": LkModule.SPEARS, "kind": spconf.kind], spconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void spearsDumpConfig ()
    {
        writeln (db.getConfig!(LkModule.SPEARS, SpearsConfig).serializeToPrettyJson);
    }

    void spearsAddHint (string sourceSuite, string targetSuite, string hint, string reason)
    {
        SpearsHint bhint;
        bhint.hint = hint;
        bhint.reason = reason;
        bhint.date = currentTimeAsBsonDate ();

        auto spearsConf = db.getConfig! (LkModule.SPEARS, SpearsConfig);
        auto coll = db.collConfig;

        foreach (ref migration; spearsConf.migrations) {
            if ((migration.sourceSuite == sourceSuite) && (migration.targetSuite == targetSuite)) {
                migration.hints ~= bhint;

                coll.findAndModify (["module": LkModule.SPEARS, "kind": spearsConf.kind], spearsConf);
                return;
            }
        }

        writefln ("Hint was not added, %s-to-%s migration entry was not found.", sourceSuite, targetSuite);
    }

    void spearsRemoveHint (string sourceSuite, string targetSuite, string hint)
    {
        import std.algorithm : remove;

        auto spearsConf = db.getConfig! (LkModule.SPEARS, SpearsConfig);
        auto coll = db.collConfig;

        foreach (ref migration; spearsConf.migrations) {
            if ((migration.sourceSuite == sourceSuite) && (migration.targetSuite == targetSuite)) {
                for (uint i; i < migration.hints.length; i++) {
                    auto bhint = migration.hints[i];
                    if (bhint.hint == hint) {
                        migration.hints = migration.hints.remove (i);

                        coll.findAndModify (["module": LkModule.SPEARS, "kind": spearsConf.kind], spearsConf);
                        return;
                    }
                }
            }
        }

        writeln ("Hint was not found.");
    }

}
