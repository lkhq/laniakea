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

public import laniakea.db.schema.core : LkModule;
public import laniakea.db.lkid : LkId, LkidType;
public import dpq2 : QueryParams, ValueFormat;
public import vibe.data.json : Json, serializeToJsonString;
public import vibe.data.bson : Bson, deserializeBson;
public import std.typecons : Nullable;


alias PgConnection = LockedConnection!__Conn;
alias PgRow = immutable(Row);

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
        //! assert (PQlibVersion() >= 9_5000);

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
    void dropConnection (ref PgConnection conn) @trusted
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

        auto conn = getConnection ();
        scope (exit) dropConnection (conn);

        // ensure we have the debversion extension loaded for this database
        conn.exec ("CREATE EXTENSION IF NOT EXISTS debversion;");

        foreach (ref schemaMod; __laniakea_db_schema_names) {
            callSchemaFunction! ("createTables", schemaMod);
        }
    }

    /**
     * Update a configuration entry for s specific module.
     */
    void updateConfigEntry (T) (PgConnection conn, LkModule mod, string key, T data) @trusted
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
     * Modify an existing config entry
     */
    void modifyConfigEntry (string id, string value) @trusted
    {
        auto conn = getConnection ();
        scope (exit) dropConnection (conn);
        QueryParams p;
        p.sqlCommand = "UPDATE config SET
                          data = $2::jsonb
                        WHERE id=$1";
        p.argsFromArray = [id, value];
        conn.execParams (p);
    }

    /**
     * Get configuration entry of the selected type T.
     */
    auto getConfigEntry (T) (PgConnection conn, LkModule mod, string key) @trusted
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

public void setParams (A...) (ref QueryParams p, A args)
{
    import laniakea.db.lkid;
    import std.datetime : SysTime, DateTime;
    import std.conv : to;
    import std.traits : OriginalType, isArray;
    import std.array : empty;
    import dpq2 : OidType, toValue;

    p.args.length = args.length;
    foreach (i, c; args) {
        alias T = typeof(c);

        static if (is(T == LkId)) {
            if ((c[0] == '\0') || (c == ""))
                p.args[i] = Value ([], OidType.Void, false, ValueFormat.BINARY);
            else
                p.args[i] = to!string (c).toValue; //! Value (cast(ubyte[])c, OidType.FixedString, false, ValueFormat.BINARY);
        } else static if (is(T == string)) {
            // since isArray is true for strings, we special-case them here, so they don't get stores as JSONB
            p.args[i] = c.toValue;
        } else {
            static if (is(T == SysTime))
                p.args[i] = c.toUnixTime.toValue;
            else static if (is(T == DateTime))
                p.args[i] = SysTime(c).toUnixTime.toValue;
            else static if (is(OriginalType!T == int))
                p.args[i] = (cast(int)c).toValue;
            else static if ((is(OriginalType!T == struct)) || (isArray!T))
                p.args[i] = c.serializeToJsonString.toValue;
            else
                p.args[i] = c.toValue;
        }
    }
}

/**
 * Convert rows of a database reply to the selected type.
 */
auto rowsTo (T) (immutable Answer ans)
{
    import std.traits : OriginalType;
    static assert (is(OriginalType!T == struct));

    T[] res;
    res.length = ans.length;

    uint i = 0;
    foreach (r; rangify (ans)) {
        res[i] = T(r);
        i++;
    }

    return res;
}

/**
 * Convert first row of a database reply to the selected type.
 */
auto rowsToOne (T) (immutable Answer ans)
{
    import std.traits : OriginalType;
    static assert (is(OriginalType!T == struct));

    Nullable!T res;
    if (ans.length > 0) {
        res = T(ans[0]);
    }

    return res;
}

/**
 * Convert a row of a database reply to the selected type.
 */
auto rowTo (T) (PgRow r)
{
    import std.traits : OriginalType;
    static assert (is(OriginalType!T == struct));
    Nullable!T res;
    if (r.length > 0) {
        res = T(r);
    }
    return res;
}

public auto dbValueTo (T) (immutable(Value) v)
{
    import laniakea.db.lkid;
    import std.datetime : SysTime, DateTime;
    import std.traits : OriginalType, isArray;
    import std.conv : to;
    import dpq2.conv.to_d_types : TimeStampWithoutTZ;
    import dpq2.oids : OidType;
    import dpq2 : as;

    static if ((is(T == string)) || (is(OriginalType!T == string)))
        return v.as!string; // we need to catch strings explicitly, because isArray is true for them
    else static if (is(T == LkId))
        return (v.isNull || v.data.length < LKID_LENGTH)? cast(LkId) "" : (cast(const(char[])) v.data).to!string;
    else static if (is(T == DateTime))
        return (as! (TimeStampWithoutTZ) (v)).dateTime;
    else static if (is(T == SysTime))
        return SysTime((v.as!TimeStampWithoutTZ).dateTime);
    else static if ((is(OriginalType!T == struct)) || (isArray!T)) {
        const bson = v.as!Bson;
        if ((bson.type == Bson.Type.array) || (bson.type == Bson.Type.object)) {
            return bson.deserializeBson!T;
        } else {
            static if (isArray!T)
                return null;
            else
                return T();
        }
    } else static if (is(OriginalType!T == int)) {
        if (v.oidType == OidType.Int2)
            return to!T (v.as!short);
        else
            return to!T (v.as!int);
    } else {
        return v.as!T;
    }
}

public void unpackRowValues (A...) (PgRow row, A args)
{
    assert (row.length == args.length);

    foreach (i, a; args) {
        (*a) = row[i].dbValueTo! (typeof((*a)));
    }
}

/**
 * Run arbitrary SQL command.
 */
auto executeSQL (A...) (PgConnection conn, string sql, A args) @trusted
{
    QueryParams p;
    p.sqlCommand = sql;
    p.setParams (args);

    return conn.execParams (p);
}
