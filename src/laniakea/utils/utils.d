/*
 * Copyright (C) 2016 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.utils.utils;

import std.string : split, strip;

/**
 * Check if string contains a remote URI.
 */
@safe
bool isRemote (const string uri)
{
    import std.regex;

    auto uriregex = ctRegex!(`^(https?|ftps?)://`);
    auto match = matchFirst (uri, uriregex);

    return (!match.empty);
}

/**
 * Split a string and strip whitespaces.
 */
@safe
string[] splitStrip (const string str, const string sep) pure
{
    auto res = str.split (sep);
    foreach (ref s; res)
        s = s.strip ();
    return res;
}

unittest
{
    import std.stdio;
    writeln ("TEST: ", "Misc Utils");

    // remote checks
    assert (isRemote ("http://test.com"));
    assert (isRemote ("https://example.org"));
    assert (!isRemote ("/srv/mirror"));
    assert (!isRemote ("file:///srv/test"));

    // check splitStrip
    assert ("a b c d".splitStrip (" ") == ["a", "b", "c", "d"]);
    assert ("a,  b, c,  d  ".splitStrip (", ") == ["a", "b", "c", "d"]);
}
