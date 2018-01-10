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

module webswview.webconfig;
@safe:

import std.array : appender;
import vibe.data.json;

import laniakea.localconfig;
import laniakea.db;

/**
 * Generic information visible on all pages and passed to every
 * template for rendering.
 */
struct GlobalInfo {
    string serviceName;

    ArchiveSuite[] suites;
}

final class WebConfig
{
    private {
        bool m_loaded = false;

        LocalConfig localConf;
    }

    public {
        BaseConfig baseConf;
        Database db;

        GlobalInfo ginfo;
        ushort port;
    }

    this (LocalConfig lconf)
    {
        localConf = lconf;
        db = Database.get;

        baseConf = db.getBaseConfig;
    }

    @trusted
    void loadFromFile (string fname)
    in { assert (!m_loaded); }
    body
    {
        import std.stdio;

        auto f = File (fname, "r");
        auto jsonData = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            jsonData ~= line;

        auto jroot = parseJsonString (jsonData.data, fname);

        ginfo.serviceName = baseConf.projectName;
        if ("ServiceName" in jroot)
            ginfo.serviceName = jroot["ServiceName"].to!string;

        port = 8080;
        if ("Port" in jroot)
            port = jroot["Port"].to!ushort;

        m_loaded = true;
    }

    void load ()
    {
        immutable confFilePath = getConfigFile ("swview-web-config.json");
        loadFromFile (confFilePath);
    }
}
