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

module laniakea.db.database;
@trusted:

import std.typecons : Nullable;
import std.string : format;
import std.array : empty;

import vibe.db.mongo.mongo;
import laniakea.localconfig;
import laniakea.logging;

import laniakea.db.schema;

/**
 * A connection to the Laniakea database.
 */
final class Database
{
    // Thread local
    private static bool instantiated_;

    // Thread global
    private __gshared Database instance_;

    @trusted
    static Database get ()
    {
        if (!instantiated_) {
            synchronized (Database.classinfo) {
                if (!instance_)
                    instance_ = new Database ();

                instantiated_ = true;
            }
        }

        return instance_;
    }

private:
    MongoClient client;
    MongoDatabase db;
    immutable string databaseName;
    immutable string mongoUrl;

    private this ()
    {
        auto conf = LocalConfig.get ();
        databaseName = conf.databaseName;
        mongoUrl = conf.mongoUrl;

        client = connectMongoDB (mongoUrl);
        db = client.getDatabase (databaseName);
    }

public:

    auto getCollection (const string name)
    {
        return db[name];
    }

    void fsync ()
    {
        db.fsync ();
    }

    auto configBase ()
    {
        return db["config.base"];
    }

    auto getBaseConfig ()
    {
        auto bconf = configBase.findOne!BaseConfig (["kind": BaseConfigKind.PROJECT]);

        // Sanity check
        DistroSuite develSuite;
        DistroSuite incomingSuite;
        foreach (ref suite; bconf.suites) {
            if (suite.name == bconf.archive.develSuite) {
                develSuite = suite;
                continue;
            } else if (suite.name == bconf.archive.incomingSuite) {
                incomingSuite = suite;
                continue;
            }
        }

        if (bconf.isNull)
            throw new Exception ("No base configuration was found in the database. Is Laniakea set up correctly?");

        if (develSuite.name.empty)
            throw new Exception ("Could not find definition of development suite %s.".format (bconf.archive.develSuite));
        if (incomingSuite.name.empty)
            throw new Exception ("Could not find definition of incoming suite %s.".format (bconf.archive.incomingSuite));

        return bconf.get;
    }

    auto getSuite (string suiteName)
    {
        Nullable!DistroSuite result;

        auto bconf = getBaseConfig;
        foreach (suite; bconf.suites) {
            if (suite.name == suiteName) {
                result = suite;
                break;
            }
        }

        return result;
    }

    auto configSynchrotron ()
    {
        return db["config.synchrotron"];
    }

    auto getSynchrotronConfig ()
    {
        auto syconf = configSynchrotron.findOne!SynchrotronConfig (["kind": SynchrotronConfigKind.BASE]);
        if (syconf.isNull)
            throw new Exception ("No Synchrotron configuration was found in the database.");
        return syconf.get;
    }

    auto getSynchrotronBlacklist ()
    {
        return configSynchrotron.findOne!SynchrotronBlacklist (["kind": SynchrotronConfigKind.BLACKLIST]);
    }

    auto configEggshell ()
    {
        return db["config.eggshell"];
    }

    auto getEggshellConfig ()
    {
        auto econf = configEggshell.findOne!EggshellConfig (["kind": EggshellConfigKind.BASE]);
        if (econf.isNull)
            throw new Exception ("No Eggshell configuration was found in the database. Can not continue.");
        return econf.get;
    }

    auto configSpears ()
    {
        return db["config.spears"];
    }

    auto getSpearsConfig ()
    {
        auto sconf = configSpears.findOne!SpearsConfig (["kind": SpearsConfigKind.BASE]);
        if (sconf.isNull)
            throw new Exception ("Unable to find Spears configuration in the database. Can not continue.");
        return sconf.get;
    }

    auto jobs ()
    {
        return db["jobs"];
    }

    void addJob (ref Job job)
    {
        job.id = BsonObjectID.generate ();
        jobs.insert (job);
    }

    auto logs ()
    {
        return db["log"];
    }

    void addLogEntry (LogEntrySeverity severity, string origin, string title, string content)
    {
        import std.datetime : Clock;
        LogEntry entry;
        entry.id = BsonObjectID.generate ();

        entry.time = BsonDate (Clock.currTime);
        entry.severity = severity;
        entry.moduleName = origin;
        entry.title = title;
        entry.content = content;

        logs.insert (entry);
    }
}
