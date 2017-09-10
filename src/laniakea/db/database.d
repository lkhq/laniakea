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

import laniakea.db.schema.core;

public import dpq2 : QueryParams, ValueFormat;
public import vibe.data.json : Json, serializeToJsonString;
public import vibe.data.bson : Bson, deserializeBson;

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

        if (!loggingIsVerbose) {
            // disable excess log messages unless we are in verbose mode
            auto conn = getConnection ();
            scope (exit) dropConnection (conn);
            conn.exec ("SET client_min_messages = warning;");
        }
    }

public:

    /**
     * Retrieve a new connection to the database.
     */
    auto getConnection () @trusted
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
    void dropConnection (ref LockedConnection!__Conn conn) @trusted
    {
        delete conn;
    }

    /**
     * Call functions on a module with this database as parameter.
     */
    void callSchemaFunction (string fun, string mod_name) ()
    {
        static import laniakea.db.schema;
        mixin("alias mod = laniakea.db.schema." ~ mod_name ~ ";");

        foreach (m; __traits(derivedMembers, mod)) {
        static if (__traits(isStaticFunction, __traits(getMember, mod, m)))
            static if (m == fun)
                __traits(getMember, mod, m) (this);
        }
    }

    /**
     * Create database and all tables
     */
    void initializeDatabase ()
    {
        import laniakea.db.schema : __laniakea_db_schema_names;

        foreach (ref schemaMod; __laniakea_db_schema_names) {
            callSchemaFunction! ("createTables", schemaMod);
        }
    }

    /**
     * Update a configuration entry for s specific module.
     */
    void updateConfigEntry (T) (LockedConnection!__Conn conn, LkModule mod, string key, T data) @trusted
    {
        QueryParams p;
        p.sqlCommand = "INSERT INTO config (id, data)
                        VALUES ($1, $2::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                        data = $2::jsonb";
        p.argsFromArray = [mod ~ "." ~ key, data.serializeToJsonString];
        conn.execParams (p);
    }

    /**
     * Update a configuration entry using an internal database connection.
     */
    void updateConfigEntry (T) (LkModule mod, string key, T data) @trusted
    {
        auto conn = getConnection ();
        scope (exit) dropConnection (conn);
        updateConfigEntry (conn, mod, key, data);
    }

    /**
     * Get configuration entry of the selected type T.
     */
    auto getConfigEntry (T) (LockedConnection!__Conn conn, LkModule mod, string key) @trusted
    {
        QueryParams p;
        p.sqlCommand = "SELECT * FROM config WHERE id=$1";
        p.argsFromArray = [mod ~ "." ~ key];
        auto r = conn.execParams(p);

        T d;
        if (r.length == 0)
            return d;
        if (r[0].length < 2)
            return d;
        immutable bson = r[0][1].as!Bson;

        // special-case some easy types
        static if (is(T == string)) {
            return bson.get!string;
        } else {
            // generic Bson deserialization
            return bson.deserializeBson!T;
        }
    }
}
