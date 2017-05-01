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

module rubicon.rubiconfig;
@safe:

import std.array : appender, empty;
import vibe.data.json;

import laniakea.localconfig;

/**
 * Rubicon local configuration.
 */
final class RubiConfig
{
    private {
        bool m_loaded = false;

        LocalConfig localConf;
    }

    public {
        string logStorageDir;
        string rejectedDir;

        string isotopeRootDir;

        string[] trustedGpgKeyrings;
    }

    this (LocalConfig lconf)
    {
        localConf = lconf;
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

        if ("LogStorage" !in jroot)
            throw new Exception ("No 'LogStorage' entry in Rubicon configuration: We need to know where to store log files.");
        logStorageDir = jroot["LogStorage"].get!string;

        if ("RejectedDir" !in jroot)
            throw new Exception ("No 'RejectedDir' entry in Rubicon configuration: We need to know where to place rejected files.");
        rejectedDir = jroot["RejectedDir"].get!string;

        trustedGpgKeyrings = localConf.trustedGpgKeyrings;
        if (trustedGpgKeyrings.empty)
            throw new Exception ("No trusted GPG keyrings were found. Ensure 'TrustedGpgKeyringDir' entry in the general configuration is set properly.");

        if ("IsotopeRootDir" in jroot)
            isotopeRootDir = jroot["IsotopeRootDir"].get!string;

        m_loaded = true;
    }

    void load ()
    {
        immutable confFilePath = getConfigFile ("rubicon.json");
        loadFromFile (confFilePath);
    }
}
