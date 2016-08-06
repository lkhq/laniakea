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

module laniakea.downloadmanager;

import std.stdio;
import std.path : buildPath, baseName;
import std.array : appender;
import requests;

import laniakea.config : Config;
import laniakea.utils : GENERIC_BUFFER_SIZE;


/**
 * Download content from the internet and cache it
 * if necessary.
 * NOTE: This class isn't very smart about re-downloading stuff yet.
 * At time it will simply always download stuff again.
 */
class DownloadManager
{

private:
    string rootDir;
    bool realFileNames;

public:

    this (string prefix = "")
    {
        auto conf = Config.get ();
        rootDir = buildPath (conf.cacheDir, urlToName (prefix));
    }

    @property @safe
    bool useRealFileNames () { return realFileNames; };
    @property @safe
    void useRealFileNames (bool v) { realFileNames = v; };

    @property @safe
    string root () { return rootDir; };

    /**
     * Get the hex string hash from another string.
     */
    @safe pure
    private string hashString (string str)
    {
        import std.digest.sha;
        auto hash = sha256Of (str);
        return toHexString (hash).dup;
    }

    /**
     * Convert an URL into a filename we can use to store the downloaded
     * file in the cache.
     */
    @safe pure
    private string urlToName (string url)
    {
        import std.string;

        if (url.empty)
            return url;

        auto res = url
                    .replace ("http:/", "")
                    .replace ("https:/", "")
                    .replace ("ftp:/", "");
        if (res.startsWith ("/"))
            res = res[1..$];

        res = res.replace ("/", "_").replace (":", "_");
        return res;
    }

    /**
     * Download a file and retrieve a filename.
     */
    string getFile (string url, bool force = false)
    {
        string targetFname;
        if (realFileNames)
            targetFname = buildPath (rootDir, baseName (url));
        else
            targetFname = buildPath (rootDir, hashString (url));

        auto content = getContent (url);

        auto f = File (targetFname, "wb");
        f.rawWrite (content.data);
        f.close ();

        return targetFname;
    }

    /**
     * Download a file and retrieve its contents in memory.
     */
    ubyte[] getFileData (string url, bool force = false)
    {
        auto fname = getFile (url, force);

        auto res = appender!(ubyte[]);
        auto f = File (fname, "r");
        while (!f.eof) {
            ubyte[GENERIC_BUFFER_SIZE] buf;
            res ~= f.rawRead (buf);
        }

        return res.data;
    }

}

unittest
{
    writeln ("TEST: ", "DownloadManager");

    auto dlm = new DownloadManager ("https://ftp.example.org/debian");

    // ensure we filenameify the prefix we just passed into the download-manager
    assert (dlm.rootDir == "ftp.example.org_debian");
}
