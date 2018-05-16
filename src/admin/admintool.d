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

import laniakea.db;
public import laniakea.cmdargs;
public import laniakea.utils : currentDateTime;
public import vibe.data.json : serializeToPrettyJson;


/**
 * Base class for CLI admin tools.
 */
abstract class AdminTool
{

private:
    string m_currentMsg;

protected:
    Database db;

    final string readString (bool allowEmpty = false)
    {
        import std.string : strip;
        import std.stdio : readln, write;
        string s;
        do {
            s = readln ();
            s = s.strip;
            if (allowEmpty)
                break;
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

    final void writeQL (string msg)
    {
        import std.stdio;
        m_currentMsg = format ("%s [list]: ", msg);
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

    final void writeDone (string msg)
    {
        writeln ("-> ", msg,);
    }

    final void writeNote (string msg)
    {
        writeln ("! ", msg,);
    }

public:

    this ()
    {
        db = Database.get ();
    }

    @property
    SubcommandInfo toolInfo ()
    {
        return SubcommandInfo ("unknown", "Dummy text");
    }

    abstract void printHelp (string progname)
    {
        printHelpText (progname, toolInfo.summary, "???", [], [], toolInfo.name);
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
bool setLaniakeaDbConfValue (string id, string value)
{
    auto db = Database.get;
    db.modifyConfigEntry (id, value);

    return true;
}
