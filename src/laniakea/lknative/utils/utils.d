/*
 * Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
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

module lknative.utils.utils;
@safe:

import std.stdio : File, writeln;
import std.string : split, strip, toLower;
import std.digest.sha : isDigest;
import std.array : appender, empty;
import std.datetime : SysTime, DateTime;
import std.uuid : UUID;

/**
 * Check if string contains a remote URI.
 */
bool isRemote (const string uri)
{
    import std.regex;

    auto uriregex = ctRegex!(`^(https?|ftps?)://`);
    auto match = matchFirst (uri, uriregex);

    return (!match.empty);
}

/**
 * Split a string and strip whitespaces.
 * Also only strip once per whitespace and ignore empty elements.
 */
string[] splitStrip (const string str, const string sep) pure
{
    auto res = appender!(string[]);
    auto splt = str.split (sep);
    foreach (ref s; splt) {
        if (s.empty)
            continue;
        res ~= s.strip;
    }
    return res.data;
}

/**
 * Generate a cryptographic hashsum for the contents of a
 * given file and return the hash as hex string.
 */
@trusted
string hashFile (Hash) (const string fname)
if (isDigest!Hash)
{
    import std.digest.sha : digest, toHexString;

    auto file = File (fname);
    auto result = digest!Hash (file.byChunk (4096 * 1024));

    return toHexString (result).toLower;
}

/**
 * Get debian revision string from a version number.
 * Params:
 *     fullVersionForNative: Return the full version if we have a native package.
 */
string getDebianRev (const string ver, bool fullVersionForNative = true)
{
    import std.string : lastIndexOf;

    immutable idx = ver.lastIndexOf ('-');
    if (idx < 0)
        return fullVersionForNative? ver : null;
    return ver[idx+1..$];
}

string[] findFilesBySuffix (string dir, string suffix) @trusted
{
    import std.file;
    import std.string : endsWith;

    auto files = appender!(string[]);
    foreach (DirEntry e; dirEntries (dir, SpanMode.shallow, true)) {
        if (e.name.endsWith (suffix))
            files ~= e.name;
    }

    return files.data;
}

public auto getPastEventAge (SysTime eventTime)
{
    import std.datetime;
    import core.time : Duration;

    auto currentTime = Clock.currTime();
    currentTime.fracSecs = Duration.zero;
    eventTime.fracSecs = Duration.zero;

    return currentTime - eventTime;
}

public auto getPastEventAge (DateTime eventTime)
{
    return getPastEventAge (SysTime (eventTime));
}

public auto randomString (uint len)
{
    import std.ascii;
    import std.range : iota;
    import std.conv : to;
    import std.algorithm : map;
    import std.random : uniform;
    assert (len > 0);

    auto pickOne(R)(R range) {
        return range[uniform(0, range.length)];
    }

    return iota (len).map! ((_) => pickOne (letters)).to!string;
}

/**
 * Read the current time and return it as DateTime
 */
auto currentDateTime ()
{
    import std.conv : to;
    import std.datetime : Clock, DateTime;
    return Clock.currTime.to!DateTime;
}

/**
 * Get a two-character ID for the specific Laniakea ID, for
 * use in directory names.
 * This version operates on strings instead of LkIds.
 */
auto getDirShorthandForUUIDString (const string id)
{
    assert (id.length > 2);
    return id[0..2];
}

/**
 * Get a two-character ID for the specific Laniakea ID, for
 * use in directory names.
 */
auto getDirShorthandForUUID (const UUID uuid)
{
    return getDirShorthandForUUIDString (uuid.toString).dup;
}

/**
 * Check if given arch `arch` matches the other arch `archAlias`. This is most
 * useful for the complex any-* rules.
 */
bool archMatches (string archAlias, string arch)
{
    import std.array : array;
    import std.string : endsWith;
    import std.algorithm : canFind, splitter;
    import std.process : execute;

    if (arch == archAlias)
        return true;

    // These pseudo-arches does not match any wildcards or aliases
    if ((arch == "all") || (arch == "source"))
        return false;

    // The 'any' wildcard matches all *real* architectures
    if (archAlias == "any")
        return true;

    // GNU/Linux arches are named <cpuabi>
    // Other Linux arches are named <libc>-linux-<cpuabi>
    if (archAlias == "linux-any")
        return !arch.canFind ("-") || arch.splitter ('-').canFind ("linux");

    if (!arch.canFind ("-") && !archAlias.canFind ("-"))
        return false;

    // This is a performance disaster
    // Hopefully we'll rarely get here
    auto dpkga = execute(["/usr/bin/dpkg-architecture",
                          "-a" ~ arch,
                          "-i" ~ archAlias
    ]);

    return dpkga.status == 0;
}

/**
 * Check if any of the given architectures in `archAliases` matches
 * architecture `arch`.
 */
bool archMatches (string[] archAliases, string arch)
{
    foreach (ref aa; archAliases) {
        if (aa.archMatches (arch))
            return true;
    }
    return false;
}

/**
 * Parse an UUID, but handle empty strings well.
 */
UUID safeParseUUID (string uuidStr)
{
    import std.array : empty;
    if (uuidStr.empty)
        return UUID ();
    return UUID (uuidStr);
}

/**
 * Read a JSON file into a Vibe.d JSON data structure.
 */
auto readJsonFile (string fname) @trusted
{
    import vibe.data.json : parseJsonString;

    auto f = File (fname, "r");
    auto jsonData = appender!string;
    string line;
    while ((line = f.readln ()) !is null)
        jsonData ~= line;

    return parseJsonString (jsonData.data, fname);
}

unittest
{
    // remote checks
    assert (isRemote ("http://test.com"));
    assert (isRemote ("https://example.org"));
    assert (!isRemote ("/srv/mirror"));
    assert (!isRemote ("file:///srv/test"));

    // check splitStrip
    assert ("a b c d".splitStrip (" ") == ["a", "b", "c", "d"]);
    assert ("a,  b, c,  d  ".splitStrip (", ") == ["a", "b", "c", "d"]);

    // check getting Debian revision numbers
    assert (getDebianRev ("1.0-3") == "3");
    assert (getDebianRev ("2.0", false) == null);
    assert (getDebianRev ("2.0") == "2.0");
    assert (getDebianRev ("-4") == "4");
    assert (getDebianRev ("2.4a-", false) == null);
    assert (getDebianRev ("2.4tanglu1") == "2.4tanglu1");
    assert (getDebianRev ("2.6~a-0tanglu4") == "0tanglu4");

    // test dir shorthand generation
    assert ("5924c600-f41a-11e7-8c3f-9a214cf093ae".getDirShorthandForUUIDString == "59");
    assert (UUID ("5924c600-f41a-11e7-8c3f-9a214cf093ae").getDirShorthandForUUID == "59");

    // architecture alias matches
    assert (archMatches ("any", "amd64"));
    assert (archMatches ("linux-any", "amd64"));
    assert (!archMatches ("linux-any", "kfreebsd-amd64"));
    assert (!archMatches ("musl-any-any", "amd64"));
    assert (archMatches ("gnu-any-any", "amd64"));
    assert (archMatches ("gnu-any-any", "linux-amd64"));
    assert (!archMatches ("gnu-any-any", "musl-linux-amd64"));
    assert (archMatches ("any-arm", "armhf"));

    assert (archMatches (["armhf", "amd64"], "amd64"));
    assert (!archMatches (["any-arm", "kfreebsd-amd64"], "amd64"));
}
