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

module admin.admintool;

import std.stdio : writeln, writefln, readln;
import std.string : format;

import vibe.db.mongo.mongo;
import laniakea.db;
import laniakea.pkgitems;


/**
 * Perform various administrative actions.
 */
final class AdminTool
{

private:
    Database db;

    string m_currentMsg;


    final string readString ()
    {
        import std.string;
        import std.stdio;
        string s;
        do {
            s = readln ();
            s = s.strip;
            if (s.empty)
                write (m_currentMsg);
        } while (s.empty);
        return s;
    }

    final string[] readList ()
    {
        import std.array : split;
        auto s = readString ();
        return s.split (" ");
    }

    final bool readBool ()
    {
        import std.string;

        auto s = readString ();
        if ((s == "y") || (s == "yes") || (s == "Y"))
            return true;
        else if ((s == "n") || (s == "no") || (s == "N"))
            return false;
        else {
            writeln ("Unknown input, assuming \"No\".");
            return false;
        }
    }

    final int readInt ()
    {
        import std.stdio;
        import std.conv : to;

        while (true) {
            auto s = readString ();
            int v;
            try {
                v = to!int (s);
            } catch (Exception e) {
                write (m_currentMsg);
                continue;
            }
            return v;
        }
    }

    final void writeQS (string msg)
    {
        import std.stdio;
        m_currentMsg = format ("%s: ", msg);
        write (m_currentMsg);
    }

    final void writeQB (string msg)
    {
        import std.stdio;
        m_currentMsg = format ("%s [y/n]: ", msg);
        write (m_currentMsg);
    }

    final void writeQI (string msg)
    {
        import std.stdio;
        m_currentMsg = format ("%s [number]: ", msg);
        write (m_currentMsg);
    }

public:

    this ()
    {
        db = Database.get ();
    }

    bool baseInit ()
    {
        writeln ("Configuring base settings for Laniakea");

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

        auto coll = db.collConfig ();

        bconf.id = BsonObjectID.generate ();
        coll.remove (["module": LkModule.BASE,
                      "kind": bconf.kind]);
        coll.update (["module": LkModule.BASE,
                      "kind": bconf.kind], bconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void baseDumpConfig ()
    {
        writeln (db.getConfig!(LkModule.BASE, BaseConfig).serializeToPrettyJson);
    }

    bool synchrotronInit ()
    {
        writeln ("Configuring base settings for Synchrotron");

        SynchrotronConfig syconf;

        writeQS ("Name of the source distribution");
        syconf.sourceName = readString ();

        writeQS ("Source repository URL");
        syconf.source.repoUrl = readString ();

        bool addSuite = true;
        while (addSuite) {
            DistroSuite suite;
            writeQS ("Adding a new source suite. Please set a name");
            suite.name = readString ();

            writeQS ("List of components for suite '%s'".format (suite.name));
            foreach (ref cname; readList ()) {
                DistroComponent c;
                c.name = cname;
                suite.components ~= c;
            }

            writeQS ("List of architectures for suite '%s'".format (suite.name));
            suite.architectures = readList ();

            syconf.source.suites ~= suite;

            writeQB ("Add another suite?");
            addSuite = readBool ();
        }

        writeQS ("Default source suite");
        syconf.source.defaultSuite = readString ();

        writeQB ("Enable sync?");
        syconf.syncEnabled = readBool ();

        writeQB ("Synchronize binary packages?");
        syconf.syncBinaries = readBool ();

        auto coll = db.collConfig;

        syconf.id = BsonObjectID.generate ();
        coll.remove (["module": LkModule.SYNCHROTRON, "kind": syconf.kind]);
        coll.update (["module": LkModule.SYNCHROTRON, "kind": syconf.kind], syconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void synchrotronDumpConfig ()
    {
        writeln ("Config:");
        writeln (db.getConfig!(LkModule.SYNCHROTRON, SynchrotronConfig).serializeToPrettyJson);
        writeln ("Blacklist:");
        writeln (db.getConfig!(LkModule.SYNCHROTRON, SynchrotronBlacklist).serializeToPrettyJson);
    }

    void synchrotronBlacklistAdd (string pkg, string reason)
    {
        db.collConfig.findAndModifyExt([
                        "module": LkModule.SYNCHROTRON,
                        "kind": SynchrotronBlacklist.stringof],
                         ["$set": ["blacklist." ~ pkg: reason]], ["upsert": true]);
    }

    void synchrotronBlacklistRemove (string pkg)
    {
        db.collConfig.findAndModifyExt([
                         "module": LkModule.SYNCHROTRON,
                         "kind": SynchrotronBlacklist.stringof],
                         ["$unset": ["blacklist." ~ pkg: ""]], ["upsert": true]);
    }

    bool spearsInit ()
    {
        import std.traits;

        writeln ("Configuring settings for Spears (migrations)");

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

    bool eggshellInit ()
    {
        writeln ("Configuring settings for Eggshell (metapackages / germinator)");

        EggshellConfig esconf;

        SpearsConfigEntry migration;
        writeQS ("Git pull URL for the germinate metapackage sources");
        esconf.metaPackageGitSourceUrl = readString ();

        auto coll = db.collConfig;

        esconf.id = BsonObjectID.generate ();
        coll.remove (["module": LkModule.EGGSHELL, "kind": esconf.kind]);
        coll.update (["mdoule": LkModule.EGGSHELL, "kind": esconf.kind], esconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void eggshellDumpConfig ()
    {
        writeln (db.getConfig!(LkModule.EGGSHELL, EggshellConfig).serializeToPrettyJson);
    }

    bool setConfValue (string moduleName, string command)
    {
        bool updateData (T) (MongoCollection coll, T selector, string setExpr)
        {
            try {
                auto json = parseJsonString ("{ " ~ setExpr ~ " }");
                coll.findAndModifyExt (selector, ["$set": json], ["new": true]);
            } catch (Exception e) {
                writeln ("Update failed: ", e);
                return false;
            }

            return true;
        }

        auto coll = db.collConfig ();
        switch (moduleName) {
            case "base":
                if (!updateData (coll, ["module": LkModule.BASE,
                                        "kind": BaseConfig.stringof], command))
                    return false;
                break;
            case "synchrotron":
                if (!updateData (coll, ["module": LkModule.SYNCHROTRON,
                                        "kind": SynchrotronConfig.stringof], command))
                    return false;
                break;
            case "synchrotron.blacklist":
                if (!updateData (coll, ["module": LkModule.SYNCHROTRON,
                                        "kind": SynchrotronBlacklist.stringof], command))
                    return false;
                break;
            case "spears":
                if (!updateData (coll, ["module": LkModule.SPEARS,
                                        "kind": SpearsConfig.stringof], command))
                    return false;
                break;
            case "eggshell":
                if (!updateData (coll, ["module": LkModule.EGGSHELL,
                                        "kind": EggshellConfig.stringof], command))
                return false;
                break;
            default:
                writeln ("Unknown module name: ", moduleName);
                return false;
        }

        return true;
    }

}
