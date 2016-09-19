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
@safe:

import std.stdio;
import std.array : appender, empty;
import std.string : format, toLower, startsWith;
import std.path : dirName, getcwd, buildPath, buildNormalizedPath;
import std.conv : to;
import std.json;
import std.typecons : Nullable;
static import std.file;

import laniakea.logging;
import laniakea.utils : findFilesBySuffix;
import laniakea.pkgitems : VersionPriority;

public immutable laniakeaVersion = "0.1";

/**
 * Information about a distribution suite.
 */
struct DistroSuite
{
    string name;
    string[] architectures;
    string[] components;
}

/**
 * Information about the derivative's package archive.
 */
struct ArchiveDetails
{
    string rootPath;
    string distroTag;
    DistroSuite develSuite;
    DistroSuite incomingSuite;
}

/**
 * Configuration specific for the synchrotron tool.
 */
struct SynchrotronConfig
{
    string sourceName;
    string sourceRepoUrl;
    DistroSuite sourceSuite;
    bool syncEnabled;
    bool syncBinaries;

    string[] sourceKeyrings;
}

/**
 * Configuration specific for the spears tool.
 */
struct SpearsConfigEntry
{
    string fromSuite;
    string toSuite;

    uint[VersionPriority] delays;
}

class BaseConfig
{
    // Thread local
    private static bool instantiated_;

    // Thread global
    private __gshared BaseConfig instance_;

    @trusted
    static BaseConfig get ()
    {
        if (!instantiated_) {
            synchronized (BaseConfig.classinfo) {
                if (!instance_)
                    instance_ = new BaseConfig ();

                instantiated_ = true;
            }
        }

        return instance_;
    }

    private bool loaded;

    // Public properties
    string projectName;
    string cacheDir;
    string workspace;
    ArchiveDetails archive;

    DistroSuite[] suites;

    bool synchrotronEnabled;
    SynchrotronConfig synchrotron;

    SpearsConfigEntry[] spears;

    private this () {
        synchrotronEnabled = false;
    }

    @trusted
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
        if ("Suites" !in root)
            throw new Exception ("Configuration must define suites in a 'Suites' section.");
        if ("Workspace" !in root)
            throw new Exception ("Configuration must define a persistent working directory via 'Workspace'.");

        workspace = root["Workspace"].str;
        archive.rootPath = root["Archive"]["path"].str;
        archive.distroTag = root["Archive"]["distroTag"].str;
        auto develSuiteName = root["Archive"]["develSuite"].str;
        auto incomingSuiteName = root["Archive"]["incomingSuite"].str;

        // Suites configuration
        foreach (sname, sdetails; root["Suites"].object) {
            DistroSuite suite;
            suite.name = sname;

            foreach (ref e; sdetails["components"].array)
                suite.components ~= e.str;
            foreach (ref e; sdetails["architectures"].array)
                suite.architectures ~= e.str;

            if (suite.name == develSuiteName)
                archive.develSuite = suite;
            else if (suite.name == incomingSuiteName)
                archive.incomingSuite = suite;

            suites ~= suite;
        }

        // Sanity check
        if (archive.develSuite.name.empty)
            throw new Exception ("Could not find definition of development suite %s.".format (develSuiteName));
        if (archive.incomingSuite.name.empty)
            throw new Exception ("Could not find definition of incoming suite %s.".format (incomingSuiteName));

        // Synchrotron configuration
        if ("Synchrotron" in root) {
            auto syncConf = root["Synchrotron"];

            synchrotron.sourceName = "Debian";
            if ("sourceName" in syncConf)
                synchrotron.sourceName = syncConf["sourceName"].str;

            if ("SourceKeyringDir" in syncConf) {
                synchrotron.sourceKeyrings = findFilesBySuffix (syncConf["SourceKeyringDir"].str, ".gpg");
            }

            synchrotron.sourceSuite.name = syncConf["source"]["suite"].str;
            foreach (ref e; syncConf["source"]["architectures"].array)
                synchrotron.sourceSuite.architectures ~= e.str;
            synchrotron.sourceRepoUrl = syncConf["source"]["repoUrl"].str;

            if ("syncEnabled" in syncConf)
                synchrotron.syncEnabled = syncConf["syncEnabled"].type == JSON_TYPE.TRUE;
            if ("syncBinaries" in syncConf)
                synchrotron.syncBinaries = syncConf["syncBinaries"].type == JSON_TYPE.TRUE;
        }

        // Spears configuration
        if ("Spears" in root) {
            foreach (ref e; root["Spears"].array) {
                SpearsConfigEntry spc;

                spc.fromSuite = e["from"].str;
                spc.toSuite = e["to"].str;

                spears ~= spc;
            }
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

    Nullable!DistroSuite getSuite (string name)
    {
        Nullable!DistroSuite res;
        foreach (ref suite; suites) {
            if (suite.name == name) {
                res = suite;
                break;
            }
        }
        return res;
    }
}
