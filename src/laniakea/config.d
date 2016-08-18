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

module laniakea.config;

import std.stdio;
import std.array : appender;
import std.string : format, toLower, startsWith;
import std.path : dirName, getcwd, buildPath, buildNormalizedPath;
import std.conv : to;
import std.json;
static import std.file;

public immutable laniakeaVersion = "0.1";

/**
 * Information about a distribution suite.
 */
struct DistroSuite
{
    string name;
    string[] architectures;
}

/**
 * Information about the derivative's package archive.
 */
struct ArchiveDetails {
    string rootPath;
    DistroSuite develSuite;
    DistroSuite landingSuite;
}

/**
 * Configuration specific for the synchrotron tool.
 */
struct SynchrotronConfig {
    DistroSuite sourceSuite;
    string sourceRepoUrl;
    bool syncEnabled;
}

class Config
{
    // Thread local
    private static bool instantiated_;

    // Thread global
    private __gshared Config instance_;

    static Config get ()
    {
        if (!instantiated_) {
            synchronized (Config.classinfo) {
                if (!instance_)
                    instance_ = new Config ();

                instantiated_ = true;
            }
        }

        return instance_;
    }

    private bool loaded;

    // Public properties
    string projectName;
    string cacheDir;
    ArchiveDetails archive;

    bool synchrotronEnabled;
    SynchrotronConfig synchrotron;

    private this () {
        synchrotronEnabled = false;
    }

    void loadFromFile (string fname)
    in { assert (!loaded); }
    body
    {
        // read the configuration JSON file
        auto f = File (fname, "r");
        auto jsonData = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            jsonData ~= line;

        JSONValue root = parseJSON (jsonData.data);

        this.projectName = "Unknown";
        if ("ProjectName" in root)
            this.projectName = root["ProjectName"].str;

        cacheDir = "/var/tmp/laniakea";
        if ("CacheLocation" in root)
            cacheDir = root["CacheLocation"].str;

        if ("Archive" !in root)
            throw new Exception ("Configuration must define archive details in an 'Archive' section.");

        archive.rootPath = root["Archive"]["path"].str;
        archive.develSuite.name = root["Archive"]["develSuite"].str;
        archive.landingSuite.name = root["Archive"]["landingSuite"].str;

        // Synchrotron configuration
        if ("Synchrotron" in root) {
            synchrotronEnabled = true;
            auto syncConf = root["Synchrotron"];

            synchrotron.sourceSuite.name = syncConf["source"]["suite"].str;
            foreach (ref e; syncConf["source"]["archs"].array)
                synchrotron.sourceSuite.architectures ~= e.str;
            synchrotron.sourceRepoUrl = syncConf["source"]["repoUrl"].str;

            if ("syncEnabled" in syncConf)
                synchrotron.syncEnabled = syncConf["syncEnabled"].type == JSON_TYPE.TRUE;
        }

        loaded = true;
    }

    void load ()
    {
        immutable exeDir = dirName (std.file.thisExePath ());

        if (!exeDir.startsWith ("/usr")) {
            immutable resPath = buildNormalizedPath (exeDir, "..", "data", "archive-config.json");
            if (std.file.exists (resPath)) {
                loadFromFile (resPath);
            }
        }

        loadFromFile ("/etc/laniakea/archive-config.json");
    }
}
