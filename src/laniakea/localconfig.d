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
import std.typecons : Nullable;
import vibe.data.json : parseJsonString;
static import std.file;

public import laniakea.db.schema.core : LkModule;

import laniakea.logging;
import laniakea.utils : findFilesBySuffix;

public immutable laniakeaVersion = "0.1";

/**
 * Get a JSON file from Laniakea's local configuration
 * directory.
 */
public string getConfigFile (string fname)
{
    immutable exeDir = dirName (std.file.thisExePath ());

    if (!exeDir.startsWith ("/usr")) {
        immutable resPath = buildNormalizedPath (exeDir, "..", "data", fname);
        if (std.file.exists (resPath))
            return resPath;
    }

    return buildPath ("/etc", "laniakea", fname);
}

/**
 * Get a (shared) data file.
 */
public string getDataFile (string fname)
{
    immutable exeDir = dirName (std.file.thisExePath ());

    if (!exeDir.startsWith ("/usr")) {
        immutable resPath = buildNormalizedPath (exeDir, "..", "data", fname);
        if (std.file.exists (resPath))
            return resPath;
    }

    // prefer stuff in /usr/local
    immutable localPath = buildPath ("/usr", "local", "share", "laniakea", fname);
    if (std.file.exists (localPath))
        return localPath;

    return buildPath ("/usr", "share", "laniakea", fname);
}

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
    string url;
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

    private this () { currentModule = LkModule.UNKNOWN; }

    private {
        bool loaded;
    }

    // Public properties
    string cacheDir;
    string workspace;

    string databaseHost;
    ushort databasePort;
    string databaseName;
    string databaseUser;
    string databasePassword;
    string databaseExtraOpts;

    LocalArchiveDetails archive;
    LocalSynchrotronConfig synchrotron;

    string serviceCurveCertFname;
    string trustedCurveCertsDir;

    string[] trustedGpgKeyrings;

    string lighthouseEndpoint;

    LkModule currentModule;

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

        immutable configDir = fname.dirName;

        // read the configuration JSON file
        auto f = File (fname, "r");
        auto jsonData = appender!string;
        string line;
        while ((line = f.readln ()) !is null)
            jsonData ~= line;

        auto jroot = parseJsonString (jsonData.data);

        cacheDir = "/var/tmp/laniakea";
        if ("CacheLocation" in jroot)
            cacheDir = jroot["CacheLocation"].to!string;

        if ("Archive" !in jroot)
            throw new Exception ("Configuration must define an archive location via 'Archive'.");
        if ("Workspace" !in jroot)
            throw new Exception ("Configuration must define a persistent working directory via 'Workspace'.");

        databaseHost = "localhost";
        databasePort = 5432;
        databaseName = "laniakea";
        databaseUser = "laniakea-user";
        if ("Database" in jroot) {
            // read database properties
            const dbroot = jroot["Database"];
            if ("host" in dbroot)
                databaseHost = dbroot["host"].to!string;
            if ("port" in dbroot)
                databasePort = dbroot["port"].to!ushort;
            if ("db" in dbroot)
                databaseName = dbroot["db"].to!string;
            if ("user" in dbroot)
                databaseUser = dbroot["user"].to!string;
            if ("password" in dbroot)
                databasePassword = dbroot["password"].to!string;
            if ("extra" in dbroot)
                databaseExtraOpts = dbroot["extra"].to!string;
        }

        workspace = jroot["Workspace"].to!string;
        archive.rootPath = jroot["Archive"]["path"].to!string;
        archive.url = jroot["Archive"]["url"].to!string;

        // Local synchrotron configuration
        if ("Synchrotron" in jroot) {
            auto syncConf = jroot["Synchrotron"];

            if ("SourceKeyringDir" in syncConf) {
                synchrotron.sourceKeyrings = findFilesBySuffix (syncConf["SourceKeyringDir"].to!string, ".gpg");
            }
        }

        if ("TrustedGpgKeyringDir" in jroot)
            trustedGpgKeyrings = findFilesBySuffix (jroot["TrustedGpgKeyringDir"].to!string, ".gpg");

        if ("LighthouseEndpoint" in jroot)
            lighthouseEndpoint = jroot["LighthouseEndpoint"].to!string;

        immutable curveCertsDir = buildPath (configDir, "keys", "curve");
        trustedCurveCertsDir = buildPath (curveCertsDir, "trusted");
        serviceCurveCertFname = buildPath (curveCertsDir, "secret", "service_private.sec");

        loaded = true;
    }

    void load (LkModule mod)
    {
        immutable confFilePath = getConfigFile ("base-config.json");
        loadFromFile (confFilePath, mod);
    }
}
