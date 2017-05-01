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
import std.conv : to;

import vibe.db.mongo.mongo;
import laniakea.localconfig;
import laniakea.logging;

import laniakea.db.schema;

/**
 * A connection to the Laniakea database.
 * This singleton can be shared between fibers,
 * but not threads.
 */
final class Database
{
    // Thread local
    private static Database instance_ = null;

    @trusted
    static Database get ()
    {
        if (instance_ is null)
            instance_ = new Database ();
        return instance_;
    }

private:
    MongoClient client;
    MongoDatabase db;
    immutable string databaseName;
    immutable string mongoUrl;

    private this ()
    {
        auto conf = LocalConfig.get;
        assert (conf.currentModule != LkModule.UNKNOWN);

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

    auto collConfig ()
    {
        return db["config"];
    }

    auto getCollection (string collname) ()
    {
        mixin("return db[\"" ~ collname ~ "\"];");
    }

    auto getCollection (LkModule modname, string cname) ()
    {
        static if (modname == LkModule.UNKNOWN)
            static assert (0, "Can not get collection for invalid module.");
        static if (cname.empty)
            mixin("return db[\"" ~ modname ~ "\"];");
        else
            mixin("return db[\"" ~ modname ~ "." ~ cname ~ "\"];");
    }

    /**
     * Get a configuration of type C for module "mod".
     */
    auto getConfigMaybe (LkModule mod, C) ()
    {
        Nullable!C conf;

        auto collConf = collConfig ();
        conf = collConf.findOne!C (["module": mod,
                                    "kind": C.stringof]);
        return conf;
    }

    auto getConfig (LkModule mod, C) ()
    {
        import std.traits : fullyQualifiedName;

        auto conf = getConfigMaybe!(mod, C) ();
        if (conf.isNull)
            throw new Exception ("No '%s' configuration of type '%s' was found in the database.".format (mod,
                                    fullyQualifiedName! (C)));
        return conf.get;
    }

    auto getBaseConfig ()
    {
        auto bconf = getConfigMaybe!(LkModule.BASE, BaseConfig);

        if (bconf.isNull)
            throw new Exception ("No base configuration was found in the database. Is Laniakea set up correctly?");

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

    auto collWorkers ()
    {
        import std.typecons : tuple;
        auto workers = db["workers"];
        workers.ensureIndex ([tuple("machine_id", 1)], IndexFlags.unique);
        return workers;
    }

    auto collJobs ()
    {
        import std.typecons : tuple;
        auto jobs = db["jobs"];
        jobs.ensureIndex ([tuple("module", 1), tuple("kind", 1)]);
        jobs.ensureIndex ([tuple("trigger", 1)]);
        return jobs;
    }

    void addJob (J) (J job, BsonObjectID trigger)
    {
        auto coll = collJobs ();
        job.id = newBsonId;
        job.createdTime = currentTimeAsBsonDate;
        job.status = JobStatus.WAITING;
        job.trigger = trigger;

        // set a dummy titke for displaying information in UIs which do not
        // have knowledge of all Laniakea modules
        if (job.title.empty) {
            job.title = "%s %s job".format (job.moduleName, job.kind);
        }

        logInfo ("Adding job '%s'", newBsonId.to!string);
        coll.insert (job);
    }

    auto collEvents ()
    {
        return db["events"];
    }

    void addEvent (EventKind kind, LkModule origin, string tag, string title, string content)
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

    void addEvent (EventKind kind, string tag, string title, string content)
    {
        addEvent (kind, LocalConfig.get.currentModule, tag, title, content);
    }

    void addEvent (EventKind kind, string tag, string title)
    {
        addEvent (kind, LocalConfig.get.currentModule, tag, title, null);
    }
}

/**
 * Create a new Bson unique identifier for use with the database.
 */
auto newBsonId ()
{
    return BsonObjectID.generate ();
}

/**
 * Read the current time and return it as BsonDate
 */
auto currentTimeAsBsonDate ()
{
    import std.datetime : Clock;
    return BsonDate (Clock.currTime ());
}
