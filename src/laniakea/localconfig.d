/*
 * Copyright (C) 2016-2017 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.localconfig;
@safe:

import std.stdio;
import std.array : appender, empty;
import std.string : format, toLower, startsWith;
import std.path : dirName, getcwd, buildPath, buildNormalizedPath;
import std.conv : to;
import std.json;
import std.typecons : Nullable;
static import std.file;

public import laniakea.db.schema.basic;

import laniakea.logging;
import laniakea.utils : findFilesBySuffix;
import laniakea.db.schema.basic;

public immutable laniakeaVersion = "0.1";

/**
 * Local configuration specific for the synchrotron tool.
 */
struct LocalSynchrotronConfig
{
    string[] sourceKeyrings;
}

/**
 * Local information about the derivative's package archive.
 */
struct LocalArchiveDetails
{
    string rootPath;
}

final class LocalConfig
{
    // Thread local
    private static bool instantiated_;

    // Thread global
    private __gshared LocalConfig instance_;

    @trusted
    static LocalConfig get ()
    {
        if (!instantiated_) {
            synchronized (LocalConfig.classinfo) {
                if (!instance_)
                    instance_ = new LocalConfig ();

                instantiated_ = true;
            }
        }

        return instance_;
    }

    private bool loaded;

    // Public properties
    string cacheDir;
    string workspace;

    string databaseName;
    string mongoUrl;

    LocalArchiveDetails archive;
    LocalSynchrotronConfig synchrotron;

    LkModule currentModule;

    private this () { currentModule = LkModule.UNKNOWN; }

    void init (LkModule mod)
    {
        currentModule = mod;
    }

    @trusted
    void loadFromFile (string fname, LkModule mod)
    in { assert (!loaded); }
    body
    {
        init (mod);

        // read the configuration JSON file
        auto f = File (fname, "r");
        auto jsonData = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            jsonData ~= line;

        JSONValue root = parseJSON (jsonData.data);

        cacheDir = "/var/tmp/laniakea";
        if ("CacheLocation" in root)
            cacheDir = root["CacheLocation"].str;

        if ("Archive" !in root)
            throw new Exception ("Configuration must define a persistent working directory via 'Workspace'.");
        if ("Workspace" !in root)
            throw new Exception ("Configuration must define a persistent working directory via 'Workspace'.");

        databaseName = "laniakea";
        mongoUrl = "mongodb://localhost/";
        if ("Database" in root) {
            // read database properties
            if ("mongoUrl" in root["Database"].object)
                mongoUrl = root["Database"]["mongoUrl"].str;
            if ("db" in root["Database"].object)
                databaseName = root["Database"]["db"].str;
        }

        workspace = root["Workspace"].str;
        archive.rootPath = root["Archive"]["path"].str;

        // Local synchrotron configuration
        if ("Synchrotron" in root) {
            auto syncConf = root["Synchrotron"];

            if ("SourceKeyringDir" in syncConf) {
                synchrotron.sourceKeyrings = findFilesBySuffix (syncConf["SourceKeyringDir"].str, ".gpg");
            }
        }

        loaded = true;
    }

    void load (LkModule mod)
    {
        immutable exeDir = dirName (std.file.thisExePath ());

        if (!exeDir.startsWith ("/usr")) {
            immutable resPath = buildNormalizedPath (exeDir, "..", "data", "archive-config.json");
            if (std.file.exists (resPath)) {
                loadFromFile (resPath, mod);
            }
        }

        loadFromFile ("/etc/laniakea/archive-config.json", mod);
    }
}
