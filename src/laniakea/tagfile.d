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

module laniakea.tagfile;
@safe:

import std.stdio;
import std.string;
import std.array : appender;
import std.conv : to;
import std.path : buildPath;

import laniakea.utils : splitStrip;
import laniakea.compressed;
import laniakea.pkgitems;

/**
 * Parser for Debians RFC2822-style metadata.
 */
class TagFile
{

private:
    string[] content;
    uint pos;

public:

    this ()
    {
    }

    void open (string fname)
    {
        auto data = decompressFile (fname);
        load (data);
    }

    void load (string data)
    {
        content = data.splitLines ();
        pos = 0;
    }

    void first () {
        pos = 0;
    }

    bool nextSection () pure
    {
        bool breakNext = false;
        auto clen = content.length;

        if (pos >= clen)
            return false;

        uint i;
        for (i = pos; i < clen; i++) {
            if (content[i] == "") {
                pos = i + 1;
                breakNext = true;
            } else if (breakNext) {
                break;
            }
        }

        // check if we reached the end of this file
        if (i == clen)
            pos = cast(uint) clen;

        if (pos >= clen)
            return false;

        return true;
    }

    string readField (string name, string defaultValue = null) pure
    {
        auto clen = content.length;

        for (auto i = pos; i < clen; i++) {
            if (content[i] == "")
                break;

            auto fdata = chompPrefix (content[i], name ~ ":");
            if (fdata == content[i])
                continue;

            if ((i+1 >= clen)
                || (!startsWith (content[i+1], " "))) {
                    // we have a single-line field
                    return strip (fdata);
            } else {
                // we have a multi-line field
                auto fdata_ml = strip (fdata);
                for (auto j = i+1; j < clen; j++) {
                    auto slice = chompPrefix (content[j], " ");
                    if (slice == content[j])
                        break;

                    if (fdata_ml == "")
                        fdata_ml = slice;
                    else
                        fdata_ml ~= "\n" ~ slice;
                }

                return fdata_ml;
            }
        }

        // we found nothing
        return defaultValue;
    }
}

/**
 * Parse a "Package-List" field and return its information in
 * PackageInfo data structures.
 * See https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Package-List
 */
public PackageInfo[] parsePackageListString (const string pkgListRaw, const string defaultVersion = null) pure @safe
{
    import std.string : splitLines;

    auto res = appender!(PackageInfo[]);
    foreach (ref line; pkgListRaw.splitLines) {
        auto parts = line.strip.split (" ");
        if (parts.length < 4)
            continue;

        PackageInfo pi;
        pi.name = parts[0];
        pi.ver = defaultVersion;
        pi.type = debTypeFromString (parts[1]);
        pi.section = parts[2];
        pi.priority = packagePriorityFromString (parts[3]);

        if (parts.length > 4) {
            // we have additional data
            auto rawVals = parts[4].split (" ");
            foreach (ref v; rawVals) {
                if (v.startsWith ("arch=")) {
                    // handle architectures
                    pi.architectures = v[5..$].split (",");
                }
            }
        }

        res ~= pi;
    }

    return res.data;
}

public ArchiveFile[] parseChecksumsList (string dataRaw, string baseDir = null)
{
    auto files = appender!(ArchiveFile[]);
    foreach (ref fileRaw; dataRaw.split ('\n')) {
        auto parts = fileRaw.strip.splitStrip (" "); // f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955 2455 0ad_0.0.20-1.dsc
        if (parts.length != 3)
            continue;

        ArchiveFile file;
        file.sha256sum = parts[0];
        file.size = to!size_t (parts[1]);
        if (baseDir.empty)
            file.fname = parts[2];
        else
            file.fname = buildPath (baseDir, parts[2]);

        files ~= file;
    }
    return files.data;
}
