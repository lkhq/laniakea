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
    JOB = "JOB"
}

/// A database object ID used within Laniakea to refer to objects in the database
alias LkId = char[LKID_LENGTH];


private enum LKID_LENGTH = 32;

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
LkId newLkid (LkidType lkt) ()
{
    import std.conv : to;
    static assert (lkt.length <= 4, "Laniakea ID prefix must be no longer than 4 characters.");

    immutable uniqLen = LKID_LENGTH - lkt.length - 1;
    immutable LkId res = lkt ~ "-" ~ to!string (getRandomAlphanum!uniqLen);

    return res;
}

unittest
{
    import std.stdio : writeln;
    writeln ("TEST: LkID");
    
    immutable id1 = newLkid!(LkidType.JOB);
    immutable id2 = newLkid!(LkidType.JOB);
    immutable id3 = newLkid!(LkidType.JOB);

    assert (id1 != id2);
    assert (id2 != id3);
    assert (id1 != id3);

    assert (id1.length == LKID_LENGTH);

    writeln (id1);
    writeln (id2);
    writeln (id3);
}
