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


/**
 * Base class for CLI admin tools.
 */
abstract class AdminTool
{

private:
    string m_currentMsg;

protected:
    Database db;



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

    final void writeHeader (string msg)
    {
        writeln ();
        writeln ("== ", msg, " ==");
        writeln ();
    }

public:

    this ()
    {
        db = Database.get ();
    }

    @property
    string toolId ()
    {
        return "unknown";
    }

    abstract int run (string[] args);

    bool initDb ()
    {
        return true;
    }
}

/**
 * Change arbitrary values in the database.
 */
bool setLaniakeaDbConfValue (string moduleName, string command)
{
    auto db = Database.get;

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
