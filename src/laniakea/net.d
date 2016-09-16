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

module laniakea.net;

import std.stdio : File;
import std.string : startsWith;
import std.path : dirName;
import std.conv : to;
static import std.file;

import laniakea.logging;

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

private void download (const string url, ref File dest, const uint retryCount = 5) @trusted
in { assert (url.isRemote); }
body
{
    import core.time;
    import std.net.curl : CurlTimeoutException, HTTP, FTP;

    size_t onReceiveCb (File f, ubyte[] data)
    {
        f.rawWrite (data);
        return data.length;
    }

    /* the curl library is stupid; you can't make an AutoProtocol to set timeouts */
    logDebug ("Downloading: %s", url);
    try {
        if (url.startsWith ("http")) {
            auto downloader = HTTP (url);
            downloader.connectTimeout = dur!"seconds" (30);
            downloader.dataTimeout = dur!"seconds" (30);
            downloader.onReceive = ((data) => onReceiveCb (dest, data));
            downloader.perform();
        } else {
            auto downloader = FTP (url);
            downloader.connectTimeout = dur!"seconds" (30);
            downloader.dataTimeout = dur!"seconds" (30);
            downloader.onReceive = ((data) => onReceiveCb (dest, data));
            downloader.perform();
        }
        logDebug ("Downloaded %s", url);
    } catch (CurlTimeoutException e) {
        if (retryCount > 0) {
            logDebug ("Failed to download %s, will retry %d more %s",
                      url,
                      retryCount,
                      retryCount > 1 ? "times" : "time");
            download (url, dest, retryCount - 1);
        } else {
            throw e;
        }
    }
}

/**
 * Download `url` to `dest`.
 *
 * Params:
 *      url = The URL to download.
 *      fname = The location for the downloaded file.
 *      retryCount = Number of times to retry on timeout.
 */
void downloadFile (const string url, const string fname, const uint retryCount = 4) @trusted
in  { assert (url.isRemote); }
out { assert (std.file.exists (fname)); }
body
{
    import std.file;

    if (fname.exists) {
        logDebug ("Overriding file '%s' with download from '%s'.", fname, url);
        remove (fname);
    } else {
        mkdirRecurse (fname.dirName);
    }

    auto f = File (fname, "wb");
    scope (exit) f.close ();
    scope (failure) remove (fname);

    download (url, f, retryCount);
}

/**
 * Download or open `path` and return it as a string array.
 *
 * Params:
 *      path = The path to access.
 *
 * Returns: The data if successful.
 */
string[] getFileContents (const string path, const uint retryCount = 4) @trusted
{
    import core.stdc.stdlib : free;
    import core.sys.linux.stdio : fclose, open_memstream;
    import std.string : fromStringz, splitLines;

    char * ptr = null;
    scope (exit) free (ptr);

    size_t sz = 0;

    if (path.isRemote) {
        {
            auto f = open_memstream (&ptr, &sz);
            scope (exit) fclose (f);
            auto file = File.wrapFile (f);
            download (path, file, retryCount);
        }

        return to!string (ptr.fromStringz).splitLines;
    } else {
        if (!std.file.exists (path))
            throw new Exception ("No such file '%s'", path);

        return std.file.readText (path).splitLines;
    }
}
