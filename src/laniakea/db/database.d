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
public import hibernated.session : Session, SessionFactory;
public import std.typecons : Nullable;
public import std.variant : Variant;

private static __gshared int OidDebversion = -1; /// The OID of the "Debversion" type, assigned when a "Database" instance is created

/**
 * A connection to the Laniakea database.
 * This singleton is shared between threads.
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

        // we can't use the connection pool here yet, because we need to
        // retrieve the debversion OID first and register it for new connections.
        // The connection pool might try to reuse a connection that doesn't have that
        // type registered otherwise.
        auto conn = driver.connect (url, params);
        scope (exit) conn.close ();

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

        // ensure DDBC understands the debversion type
        driver.registerCuromDataType (OidDebversion);

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
                                          VALUES (?, ?::jsonb)
                                          ON CONFLICT (id) DO UPDATE SET
                                          data = ?::jsonb");
        scope (exit) ps.close ();

        immutable jdata = data.serializeToJsonString;
        ps.setString (1, mod ~ "." ~ key);
        ps.setString (2, jdata);
        ps.setString (3, jdata);
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
                                          data = ?::jsonb
                                          WHERE id=?");
        scope (exit) ps.close ();

        ps.setString (1, value);
        ps.setString (2, id);
        ps.executeUpdate ();
    }

    /**
     * Get configuration entry of the selected type T.
     */
    auto getConfigEntry (T) (Connection conn, LkModule mod, string key) @trusted
    {
        import vibe.data.json : deserializeJson, parseJsonString;

        auto ps = conn.prepareStatement ("SELECT * FROM config WHERE id=?");
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
    auto newSessionFactory (SchemaInfo schema)
    {
        return new SessionFactoryImpl (schema, dialect, dsource);
    }

    /**
     * Create a new session factory for the set entities,
     * including a couple of entities from the core set (such as ArchiveSuite)
     * by default.
     */
    auto newSessionFactory (T...) ()
    {
        import laniakea.db.schema.core;
        import laniakea.db.schema.archive;
        auto schema = new SchemaInfoImpl! (ArchiveRepository,
                                           ArchiveComponent,
                                           ArchiveArchitecture,
                                           ArchiveSuite,
                                           SourcePackage,
                                           BinaryPackage,
                                           T);
        return new SessionFactoryImpl (schema, dialect, dsource);
    }

    /**
     * Create a new session factory including entities from
     * the core set (such as ArchiveSuite and ArchiveRepository)
     */
    auto newSessionFactory ()
    {
        import laniakea.db.schema.core;
        import laniakea.db.schema.archive;
        auto schema = new SchemaInfoImpl! (ArchiveRepository,
                                           ArchiveComponent,
                                           ArchiveArchitecture,
                                           ArchiveSuite,
                                           SourcePackage,
                                           BinaryPackage);
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
