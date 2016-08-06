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

module laniakea.remoterepo;

import std.stdio;
import requests;

import laniakea.downloadmanager;
import laniakea.utils : TagFile;


/**
 * Interface with a Debian repository on a remote (ftp/http)
 * location.
 */
class RemoteRepo
{

private:
    DownloadManager dlm;

public:

    this (string repoUrl)
    {
        dlm = new DownloadManager (repoUrl);
        dlm.useRealFileNames = true;
    }

    TagFile open (string suite, string section, string arch)
    {
        // TODO

        return null;
    }

}

unittest
{
    writeln ("TEST: ", "RemoteRepo");

    auto repo = new RemoteRepo ("http://ftp.debian.org/debian");
}
