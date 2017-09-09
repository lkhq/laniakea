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

module laniakea.db.database;
@trusted:

import std.typecons : Nullable;
import std.string : format;
import std.array : empty;
import std.conv : to;

import vibe.db.postgresql;
import laniakea.localconfig;
import laniakea.logging;

import laniakea.db.basic;

public import dpq2 : QueryParams, ValueFormat;
public import vibe.data.json : Json, serializeToJsonString;

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
    PostgresClient client;

    immutable string dbHost;
    immutable ushort dbPort;
    immutable string dbName;
    immutable string dbUser;
    immutable string dbPassword;
    immutable string dbExtraOptions;

    private this ()
    {
        const conf = LocalConfig.get;
        assert (conf.currentModule != LkModule.UNKNOWN, "A module without identifier tried to access the database.");

        dbHost = conf.databaseHost;
        dbPort = conf.databasePort;
        dbName = conf.databaseName;
        dbUser = conf.databaseUser;
        dbPassword = conf.databasePassword;
        dbExtraOptions = conf.databaseExtraOpts;

        client = new PostgresClient("host=" ~ dbHost ~
                                    " port=" ~ dbPort.to!string ~
                                    " dbname=" ~ dbName ~
                                    " user=" ~ dbUser ~
                                    " password=" ~ dbPassword ~
                                    " " ~ dbExtraOptions, 8);
    }

public:

    /**
     * Retrieve a new connection to the database.
     */
    auto getConnection ()
    {
        try {
            return client.lockConnection();
        } catch (Exception e) {
            throw new Exception("Unable to get database connection: %s".format (e.msg));
        }
    }

    /**
     * Explicitly close a database connection and return its slot.
     */
    void dropConnection (ref LockedConnection!__Conn conn)
    {
        delete conn;
    }

    void updateConfigEntry (LockedConnection!__Conn conn, LkModule mod, string key, string json)
    {
        QueryParams p;
        p.sqlCommand = "INSERT INTO config (id, data)
                        VALUES ($1, $2::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                        data = $2::jsonb";
        p.argsFromArray = [mod ~ "." ~ key, json];
        conn.execParams (p);
    }

    void updateConfigEntry (LkModule mod, string key, string json)
    {
        auto conn = getConnection ();
        scope (exit) dropConnection (conn);
        updateConfigEntry (conn, mod, key, json);
    }

}
