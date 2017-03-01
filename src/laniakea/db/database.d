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

 import vibe.db.mongo.mongo;
 import laniakea.config;
 import laniakea.logging;
 import laniakea.db.schema.basic;

/**
 * A connection to the Laniakea database.
 */
class Database
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
        auto conf = BaseConfig.get ();
        databaseName = conf.databaseName;
        mongoUrl = conf.mongoUrl;

        client = connectMongoDB (mongoUrl);
        db = client.getDatabase (databaseName);
    }

public:

    final auto getCollection (const string name)
    {
        return db[name];
    }

    final void fsync ()
    {
        db.fsync ();
    }

    final auto jobs ()
    {
        return db["jobs"];
    }

    final auto configGlobal ()
    {
        return db["config.global"];
    }

    final auto configSynchrotron ()
    {
        return db["config.synchrotron"];
    }

    void addJob (ref Job job)
    {
        job.id = BsonObjectID.generate ();
        jobs.insert (job);
    }
}
