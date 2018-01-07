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

module laniakea.db.schema.core;
@safe:

public import std.array : empty;
public import std.uuid : UUID;
public import hibernated.annotations;

/**
 * A list of all modules integrated into the Laniakea suite,
 * with their respective identifier strings.
 * Any piece that uses the database *requires* a module name.
 */
enum LkModule
{
    UNKNOWN     = "",
    BASE        = "core",        /// The Laniakea base platform
    TESTSUITE   = "test",        /// The Laniakea testsuite
    LIGHTHOUSE  = "lighthouse",  /// Message relay station
    SYNCHROTRON = "synchrotron", /// Syncs packages from a source distribution
    SPEARS      = "spears",      /// Automatic package migration
    PLANTER     = "planter",     /// Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI    = "admin-cli",   /// CLI interface to Laniakea settings and the database, useful debug tool
    KEYTOOL     = "keytool",     /// Small CLI tool to handle encryption keys and certificates
    WEB         = "web",         /// Laniakea web view
    WEBSWVIEW   = "webswview",   /// Packages / software web view
    DEBCHECK    = "debcheck",    /// Package installability and dependency tests
    ISOTOPE     = "isotope",     /// ISO image build scheduling and data import
    RUBICON     = "rubicon",     /// Accepts job result artifacts (logfiles, built files, ...), verifies them and moves them to the right place
    ARCHIVE     = "archive",     /// Lists packages in the database
    DATAIMPORT  = "dataimport"   /// Import various data from other sources into the database
}

/**
 * A template to mix into classes containing a uuid primary key.
 **/
template UUIDProperty() {
    UUID uuid;
    @property @Column ("uuid") @Id @UniqueKey string uuid_s () { return uuid.toString; }
    @property void uuid_s (string s) { uuid = UUID (s); }
}

/**
 * A template to quickly add JSON/JSONB properties to database entities,
 * so Hibernated can recognize and serialize them.
 */
template JsonDatabaseField (string column, string fieldName, string dataType) {
    const char[] JsonDatabaseField =
        `@property @Column ("` ~ column ~ `")
         string ` ~ fieldName ~ `_json () {
             import vibe.data.json : serializeToJsonString;
             return serializeToJsonString (` ~ fieldName ~ `);
         };

         @property @Column ("` ~ column ~ `")
         void ` ~ fieldName ~ `_json (string v) {
             import vibe.data.json : deserializeJson;
             ` ~ fieldName ~ ` = v.deserializeJson! (` ~ dataType ~ `);
         };`;
}

/**
 * A template to make enums readable as integers for the Hibernated ORM.
 */
template EnumDatabaseField (string column, string fieldName, string dataType, bool isShort = false) {
    static if (isShort) {
        const char[] EnumDatabaseField =
            `@property @Column ("` ~ column ~ `")
            short ` ~ fieldName ~ `_i () {
                import std.conv : to;
                return ` ~ fieldName ~ `.to!short;
            };

            @property @Column ("` ~ column ~ `")
            void ` ~ fieldName ~ `_i (short v) {
                import std.conv : to;
                ` ~ fieldName ~ ` = v.to! (` ~ dataType ~ `);
            };`;
    } else {
        const char[] EnumDatabaseField =
            `@property @Column ("` ~ column ~ `")
            int ` ~ fieldName ~ `_i () {
                import std.conv : to;
                return ` ~ fieldName ~ `.to!int;
            };

            @property @Column ("` ~ column ~ `")
            void ` ~ fieldName ~ `_i (int v) {
                import std.conv : to;
                ` ~ fieldName ~ ` = v.to! (` ~ dataType ~ `);
            };`;
    }
}

/**
 * A system architecture software can be compiled for.
 * Usually associated with an @ArchiveSuite
 */
class ArchiveRepository
{
    int id;

    @UniqueKey
    string name;

    LazyCollection!ArchiveSuite suites;
}

/**
 * Information about a distribution suite.
 */
class ArchiveSuite
{
    int id;

    string name;

    ArchiveRepository repo;

    @ManyToMany
    LazyCollection!ArchiveArchitecture architectures;

    @ManyToMany
    LazyCollection!ArchiveComponent components;

    @Null
    string baseSuite;
}

/**
 * Information about a distribution component.
 */
class ArchiveComponent
{
    int id;

    @UniqueKey
    string name;

    @ManyToMany // w/o this annotation will be OneToMany by convention
    LazyCollection!ArchiveSuite suites;
}

/**
 * A system architecture software can be compiled for.
 * Usually associated with an @ArchiveSuite
 */
class ArchiveArchitecture
{
    int id;

    @UniqueKey
    string name;

    @ManyToMany
    LazyCollection!ArchiveSuite suites;

    this (string name)
    {
        this.name = name;
    }
}

/**
 * Basic archive configuration
 **/
struct BaseArchiveConfig {
    string develSuite;     /// Development target suite ("testing", "green", ...)
    string incomingSuite;  /// Suite where new packages typically arrive ("unstable", "staging", ...)
    string distroTag;      /// Version tag for this distribution ("pureos", "tanglu", ...) - will usually be part of a package version, e.g. "1.0-0tanglu1"
}

/**
 * Basic project configuration
 **/
struct BaseConfig {
    string projectName;         /// Name of the distrobution or project ("Tanglu", "PureOS", ...)
    BaseArchiveConfig archive;  /// archive specific settings
}

import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);
    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    stmt.executeUpdate (
        "CREATE TABLE IF NOT EXISTS config (
          id text PRIMARY KEY,
          data jsonb NOT NULL
        )"
    );

    auto schema = new SchemaInfoImpl! (ArchiveRepository,
                                      ArchiveSuite,
                                      ArchiveArchitecture,
                                      ArchiveComponent);

    auto factory = db.newSessionFactory (schema);
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData().updateDBSchema (conn, false, true);
}

/**
 * Add/update basic configuration.
 */
void update (Database db, BaseConfig conf)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.BASE, "projectName", conf.projectName);

    db.updateConfigEntry (conn, LkModule.BASE, "archive.develSuite", conf.archive.develSuite);
    db.updateConfigEntry (conn, LkModule.BASE, "archive.incomingSuite", conf.archive.incomingSuite);
    db.updateConfigEntry (conn, LkModule.BASE, "archive.distroTag", conf.archive.distroTag);
}

auto getBaseConfig (Database db)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    BaseConfig conf;
    conf.projectName = db.getConfigEntry!string (conn, LkModule.BASE, "projectName");
    conf.archive.develSuite = db.getConfigEntry!string (conn, LkModule.BASE, "archive.develSuite");
    conf.archive.incomingSuite = db.getConfigEntry!string (conn, LkModule.BASE, "archive.incomingSuite");
    conf.archive.distroTag = db.getConfigEntry!string (conn, LkModule.BASE, "archive.distroTag");

    return conf;
}

auto getSuite (Database db, string name, string repo = "master") @trusted
{
    auto schema = new SchemaInfoImpl! (ArchiveSuite);

    auto factory = db.newSessionFactory (schema);
    auto session = factory.openSession();
    scope (exit) session.close();

    auto q = session.createQuery ("FROM archive_suite WHERE name=:Name")
                    .setParameter ("Name", name);
    ArchiveSuite[] list = q.list!ArchiveSuite();

    if (list.empty)
        return null;
    return list[0];
}
