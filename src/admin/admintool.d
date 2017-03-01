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

import std.stdio;
import std.string : format;

import vibe.db.mongo.mongo;
import laniakea.db.database;
import laniakea.db.schema.synchrotron;


/**
 * Perform various administrative actions.
 */
class AdminTool
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

public:

    this ()
    {
        db = Database.get ();
    }

    bool synchrotronInit ()
    {
        writeln ("Configuring base settings for Synchrotron");

        SynchrotronConfig syconf;

        writeQS ("Name of the source distribution");
        syconf.sourceName = readString ();

        writeQS ("Source repository URL");
        syconf.source.repoUrl = readString ();

        writeQS ("Default source suite");
        syconf.source.defaultSuite = readString ();

        writeQS ("Sync source architectures");
        syconf.source.architectures = readList ();

        writeQB ("Enable sync?");
        syconf.syncEnabled = readBool ();

        writeQB ("Synchronize binary packages?");
        syconf.syncBinaries = readBool ();

        // TODO: Allow registering suites

        auto coll = db.configSynchrotron;

        syconf.id = BsonObjectID.generate ();
        coll.update (["kind": syconf.kind], syconf, UpdateFlags.upsert);

        db.fsync;
        return true;
    }

}
