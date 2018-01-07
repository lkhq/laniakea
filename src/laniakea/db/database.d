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

import laniakea.localconfig;
import laniakea.logging;
import ddbc;
import ddbc.drivers.pgsqlddbc : PGSQLDriver;
import hibernated.core;

import laniakea.db.utils;

public import laniakea.db.schema.core : LkModule;
public import ddbc : Connection, ResultSet;
public import hibernated.annotations;
public import hibernated.type;
public import hibernated.metadata;
public import std.typecons : Nullable;
public import std.variant : Variant;

private static __gshared int OidDebversion = -1; /// The OID of the "Debversion" type, assigned when a "Database" instance is created

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
    PGSQLDriver driver;
    DataSource dsource;
    PGSQLDialect dialect;

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


        driver = new PGSQLDriver();
        auto url = PGSQLDriver.generateUrl (dbHost, dbPort, dbName);
        auto params = PGSQLDriver.setUserAndPassword (dbUser, dbPassword);
        dsource = new ConnectionPoolDataSourceImpl (driver, url, params);

        auto conn = getConnection ();
        scope (exit) dropConnection (conn);

        if (!loggingIsVerbose) {
            // disable excess log messages unless we are in verbose mode
            auto stmt = conn.createStatement ();
            scope (exit) stmt.close ();

            stmt.executeUpdate ("SET client_min_messages = warning;");
        }

        // fetch the Debversion OID
        auto stmt = conn.createStatement ();
        scope (exit) stmt.close ();

        auto rs = stmt.executeQuery ("SELECT 'debversion'::regtype::oid::integer");
        if (!rs.first ())
            throw new Exception ("Unable to get OID for the debversion type - is the debversion extension active on Postgres?");
        OidDebversion = rs.getInt (1);

        dialect = new PGSQLDialect;
    }

public:

    /**
     * Retrieve a new connection to the database.
     */
    auto getConnection () @trusted
    {
        return dsource.getConnection ();
    }

    /**
     * Explicitly close a database connection and return its slot.
     */
    void dropConnection (ref Connection conn) @trusted
    {
        conn.close ();
    }

    /**
     * Execute a simple SQL command using a new connection.
     *
     * Using this method is not very efficient, if you need
     * to execute more than one command, use a dedicated
     * connection/statement combo.
     */
    int simpleExecute (string sql)
    {
        auto conn = getConnection ();
        scope (exit) dropConnection (conn);
        auto stmt = conn.createStatement();
        scope(exit) stmt.close();

        return stmt.executeUpdate (sql);
    }

    /**
     * Update a configuration entry for s specific module.
     */
    void updateConfigEntry (T) (Connection conn, LkModule mod, string key, T data) @trusted
    {
        import vibe.data.json : serializeToJsonString;

        auto ps = conn.prepareStatement ("INSERT INTO config (id, data)
                                          VALUES ($1, $2::jsonb)
                                          ON CONFLICT (id) DO UPDATE SET
                                          data = $2::jsonb");
        scope (exit) ps.close ();

        ps.setString (1, mod ~ "." ~ key);
        ps.setString (2, data.serializeToJsonString);
        ps.executeUpdate ();
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

        auto ps = conn.prepareStatement ("UPDATE config SET
                                          data = $2::jsonb
                                          WHERE id=$1");
        scope (exit) ps.close ();

        ps.setString (1, id);
        ps.setString (2, value);
        ps.executeUpdate ();
    }

    /**
     * Get configuration entry of the selected type T.
     */
    auto getConfigEntry (T) (Connection conn, LkModule mod, string key) @trusted
    {
        import vibe.data.json : deserializeJson, parseJsonString;

        auto ps = conn.prepareStatement ("SELECT * FROM config WHERE id=$1");
        scope (exit) ps.close ();
        ps.setString (1, mod ~ "." ~ key);
        auto rs = ps.executeQuery ();

        T d;
        if (rs.getFetchSize == 0)
            return d;
        rs.first ();

        immutable json = parseJsonString (rs.getString (2));

        // special-case some easy types
        static if (is(T == string)) {
            return json.get!string;
        } else {
            // generic Bson deserialization
            return json.deserializeJson!T;
        }
    }

    /**
     * Create a new session factory using the provided schema.
     */
    auto newSessionFactory (EntityMetaData schema)
    {
        return new SessionFactoryImpl (schema, dialect, dsource);
    }
}

/**
 * Convert rows of a database reply to the selected type.
 */
auto rowsTo (T) (ResultSet rs)
{
    import std.traits : OriginalType;
    static assert (is(OriginalType!T == struct));

    T[] res;
    res.length = rs.getFetchSize;

    uint i = 0;
    while (rs.next ()) {
        res[i] = T(rs);
        i++;
    }

    return res;
}

/**
 * Convert first row of a database reply to the selected type.
 */
auto rowsToOne (T) (ResultSet rs)
{
    import std.traits : OriginalType;
    static assert (is(OriginalType!T == struct));

    Nullable!T res;
    if (rs.getFetchSize > 0) {
        rs.first ();
        res = T(rs);
    }

    return res;
}

version (none) {
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
 * Convert rows of a database reply to a string list.
 */
auto rowsToStringList (immutable Answer ans)
{
    string[] res;
    res.length = ans.length;

    uint i = 0;
    foreach (r; rangify (ans)) {
        if (r.length <= 0)
            continue;
        res[i] = r[0].dbValueTo!string;
        i++;
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

    // special-case debversion strings
    static if ((is(T == string)) || (is(OriginalType!T == string))) {
        if (v.oidType == OidDebversion)
            return (cast(const(char[])) v.data).to!T;
    }

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

} // end of uncomment version() block
