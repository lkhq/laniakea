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

module laniakea.db.lkid;

import laniakea.db.schema.core;
@safe:

// NOTE: All of this should be @nogc, unfortunately there is no @nogc random functionality in
// the standard library. If this becomes a performance issue, we need to deal with this differently.

/**
 * Tyoe of a global Laniakea ID
 */
enum LkidType
{
    JOB               = "JOB",  /// Prefix for a generic Laniakea job
    EVENT             = "EVNT", /// A (log) event
    WORKER            = "WRK",  /// Prefix for a generic Laniakea worker
    USER              = "USR",  /// Prefix for a human user
    DEBCHECK          = "DEBC", /// Debcheck issue entry prefix
    ISOTOPE_RECIPE    = "ISOR", /// Isotope ISO image recipe prefix
    SPEARS_EXCUSE     = "SPRE", /// Spears excuse prefix
    SYNCHROTRON_ISSUE = "SYNI"  /// Synchrotron issue prefix
}

/// A database object ID used within Laniakea to refer to objects in the database
alias LkId = char[LKID_LENGTH];
public enum LKID_LENGTH = 32;


template LkidSerializationPolicy(T)
	if (is(T == LkId))
{
	import std.conv : to;
	static string toRepresentation(T value) @safe {
		return to!string(value);
	}

	static T fromRepresentation(string value) {
		LkId id = value;
		return id;
	}
}

private auto getRandomAlphanum (uint len) ()
{
    import std.algorithm : fill;
    import std.ascii : letters, digits;
    import std.conv : to;
    import std.random : randomCover, rndGen;
    import std.range : chain;

    static immutable asciiLetters = to!(dchar[]) (letters);
    static immutable asciiDigits = to!(dchar[]) (digits);

    dchar[len] data;
    fill (data[], randomCover (chain (asciiLetters, asciiDigits), rndGen));

    return data;
}

/**
 * Generate a unique Laniakea ID to identify an object in the database.
 */
LkId generateNewLkid (LkidType lkt) ()
{
    import std.conv : to;
    static assert (lkt.length <= 4, "Laniakea ID prefix must be no longer than 4 characters.");

    immutable uniqLen = LKID_LENGTH - lkt.length - 1;
    immutable LkId res = lkt ~ "-" ~ to!string (getRandomAlphanum!uniqLen);

    return res;
}

/**
 * Get a two-character ID for the specific Laniakea ID, for
 * use in directory names.
 */
auto getDirShorthandForLkid (const ref LkId id)
{
    import std.string : indexOf;
    if (id[3] == '-')
        return id[4..6];
    if (id[4] == '-')
        return id[5..7];
    immutable idx = id.indexOf ("-");
    if (idx < 0)
        return id[0..2];
    return id[idx+1..idx+3];
}

/**
 * Get a two-character ID for the specific Laniakea ID, for
 * use in directory names.
 * This version operates on strings instead of LkIds.
 */
auto getDirShorthandForLkidString (const string idstr)
{
    if (idstr.length < 10)
        throw new Exception ("String is too short to generate a dir shorthand for.");
    immutable id = idstr.to!LkId;
    return getDirShorthandForLkid (id).dup;
}

/**
 * Helper to cast a regular string into a Laniakea ID.
 */
auto to (LkId) (string s)
{
    if (s.length != LKID_LENGTH)
        assert (0, "Can not cast string into LkId, size does not match.");
    LkId id = s;
    return id;
}

unittest
{
    import std.stdio : writeln;
    writeln ("TEST: LkID");

    immutable id1 = generateNewLkid!(LkidType.JOB);
    immutable id2 = generateNewLkid!(LkidType.JOB);
    immutable id3 = generateNewLkid!(LkidType.JOB);

    assert (id1 != id2);
    assert (id2 != id3);
    assert (id1 != id3);

    assert (id1.length == LKID_LENGTH);

    writeln (id1);
    writeln (id2);
    writeln (id3);

    // test dir shorthand generation
    assert ("JOB-7oJOgaFWCEnxuKrfU4jZHQdl3tD8".getDirShorthandForLkid == "7o");
    assert ("EVNT-aiot73ifn83mdksz39enw8rfo39".getDirShorthandForLkid == "ai");
    assert ("HISHAIOD84jdhs9w37owehsd9skejwd9".getDirShorthandForLkid == "HI");
    assert ("ascbacjjua-hd7639wndosnds7ekwnsi".getDirShorthandForLkid == "hd");
    assert ("UNKNOWN_INVALID                 ".getDirShorthandForLkid == "UN");
    assert ("INVALID_STR".getDirShorthandForLkidString == "UN");
}
