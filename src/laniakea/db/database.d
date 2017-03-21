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

    auto collConfig (ModuleName modname) ()
    {
        static if (modname == ModuleName.UNKNOWN)
            static assert (0, "Can not get config for invalid module name.");
        mixin("return db[\"config." ~ modname ~ "\"];");
    }

    auto getConfig (T) () {
        import std.traits :fullyQualifiedName;

        Nullable!T conf;
        ModuleName modname;

        static if (is(T == SynchrotronConfig)) {
            modname = ModuleName.SYNCHROTRON;
            auto dbColl = collConfig!(ModuleName.SYNCHROTRON);
            conf = dbColl.findOne!T (["kind": SynchrotronConfigKind.BASE]);

        } else static if (is (T == EggshellConfig)) {
            modname = ModuleName.EGGSHELL;
            auto dbColl = collConfig!(ModuleName.EGGSHELL);
            conf = dbColl.findOne!T (["kind": EggshellConfigKind.BASE]);

        } else static if (is (T == SpearsConfig)) {
            modname = ModuleName.SPEARS;
            auto dbColl = collConfig!(ModuleName.SPEARS);
            conf = dbColl.findOne!T (["kind": SpearsConfigKind.BASE]);

        } else {
            static assert (0, "Finding configuration for " ~ fullyQualifiedName!T ~ "is not implemented.");
        }

        if (conf.isNull)
            throw new Exception ("No '%s' configuration was found in the database.".format (modname));
        return conf.get;
    }

    auto getBaseConfig ()
    {
        auto bconf = collConfig!(ModuleName.BASE).findOne!BaseConfig (["kind": BaseConfigKind.PROJECT]);

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

    auto getSynchrotronBlacklist ()
    {
        return collConfig!(ModuleName.SYNCHROTRON).findOne!SynchrotronBlacklist (["kind": SynchrotronConfigKind.BLACKLIST]);
    }

    auto collJobs ()
    {
        return db["jobs"];
    }

    void addJob (ref Job job)
    {
        job.id = BsonObjectID.generate ();
        collJobs.insert (job);
    }

    auto collEvents ()
    {
        return db["events"];
    }

    void addEvent (EventKind kind, ModuleName origin, string title, string content)
    {
        import std.datetime : Clock;
        EventEntry entry;
        entry.id = BsonObjectID.generate ();

        entry.time = BsonDate (Clock.currTime);
        entry.kind = kind;
        entry.moduleName = origin;
        entry.title = title;
        entry.content = content;

        collEvents.insert (entry);
    }
}
