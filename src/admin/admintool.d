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

import std.stdio;
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
        m_currentMsg = format ("%s: ", msg);
        write (m_currentMsg);
    }

    final void writeQB (string msg)
    {
        m_currentMsg = format ("%s [y/n]: ", msg);
        write (m_currentMsg);
    }

    final void writeQI (string msg)
    {
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
            DistroSuite suite;
            writeQS ("Adding a new suite. Please set a name");
            suite.name = readString ();

            writeQS ("List of components for suite '%s'".format (suite.name));
            suite.components = readList ();

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

        auto coll = db.collConfig!(LkModule.BASE);

        bconf.id = BsonObjectID.generate ();
        coll.remove (["kind": bconf.kind]);
        coll.update (["kind": bconf.kind], bconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void baseDumpConfig ()
    {
        writeln (db.collConfig!(LkModule.BASE).findOne (["kind": BaseConfigKind.PROJECT]).serializeToPrettyJson);
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
            suite.components = readList ();

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

        auto coll = db.collConfig!(LkModule.SYNCHROTRON);

        syconf.id = BsonObjectID.generate ();
        coll.remove (["kind": syconf.kind]);
        coll.update (["kind": syconf.kind], syconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void synchrotronDumpConfig ()
    {
        auto collSyconf = db.collConfig!(LkModule.SYNCHROTRON);
        writeln ("Config:");
        writeln (collSyconf.findOne (["kind": SynchrotronConfigKind.BASE]).serializeToPrettyJson);
        writeln ("Blacklist:");
        writeln (collSyconf.findOne (["kind": SynchrotronConfigKind.BLACKLIST]).serializeToPrettyJson);
    }

    void synchrotronBlacklistAdd (string pkg, string reason)
    {
        db.collConfig!(LkModule.SYNCHROTRON)
                        .findAndModifyExt(["kind": SynchrotronConfigKind.BLACKLIST],
                         ["$set": ["blacklist." ~ pkg: reason]], ["upsert": true]);
    }

    void synchrotronBlacklistRemove (string pkg)
    {
        db.collConfig!(LkModule.SYNCHROTRON)
                        .findAndModifyExt(["kind": SynchrotronConfigKind.BLACKLIST],
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

        auto coll = db.collConfig!(LkModule.SPEARS);

        spconf.id = BsonObjectID.generate ();
        coll.remove (["kind": spconf.kind]);
        coll.update (["kind": spconf.kind], spconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void spearsDumpConfig ()
    {
        writeln (db.collConfig!(LkModule.SPEARS).findOne (["kind": SpearsConfigKind.BASE]).serializeToPrettyJson);
    }

    bool eggshellInit ()
    {
        writeln ("Configuring settings for Eggshell (metapackages / germinator)");

        EggshellConfig esconf;

        SpearsConfigEntry migration;
        writeQS ("Git pull URL for the germinate metapackage sources");
        esconf.metaPackageGitSourceUrl = readString ();

        auto coll = db.collConfig!(LkModule.EGGSHELL);

        esconf.id = BsonObjectID.generate ();
        coll.remove (["kind": esconf.kind]);
        coll.update (["kind": esconf.kind], esconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

    void eggshellDumpConfig ()
    {
        writeln (db.collConfig!(LkModule.EGGSHELL).findOne (["kind": EggshellConfigKind.BASE]).serializeToPrettyJson);
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
        switch (moduleName) {
            case "base":
                auto coll = db.collConfig!(LkModule.BASE);
                if (!updateData (coll, ["kind": BaseConfigKind.PROJECT], command))
                    return false;
                break;
            case "synchrotron":
                auto coll = db.collConfig!(LkModule.SYNCHROTRON);
                if (!updateData (coll, ["kind": SynchrotronConfigKind.BASE], command))
                    return false;
                break;
            case "synchrotron.blacklist":
                auto coll = db.collConfig!(LkModule.SYNCHROTRON);
                if (!updateData (coll, ["kind": SynchrotronConfigKind.BLACKLIST], command))
                    return false;
                break;
            case "spears":
                auto coll = db.collConfig!(LkModule.SPEARS);
                if (!updateData (coll, ["kind": SpearsConfigKind.BASE], command))
                    return false;
                break;
            case "eggshell":
                auto coll = db.collConfig!(LkModule.EGGSHELL);
                if (!updateData (coll, ["kind": EggshellConfigKind.BASE], command))
                    return false;
                break;
            default:
                writeln ("Unknown module name: ", moduleName);
                return false;
        }

        return true;
    }

}
