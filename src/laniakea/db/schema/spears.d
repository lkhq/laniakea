/*
 * Copyright (C) 2017 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.db.schema.spears;
@safe:

import std.datetime : DateTime;

import laniakea.db.utils;
import laniakea.pkgitems : VersionPriority;


/**
 * User-defined hints for Britney.
 */
struct SpearsHint
{
    DateTime date;

    string hint;
    string reason;

    string user;
}

/**
 * Configuration specific for the Spears tool.
 */
struct SpearsConfigEntry
{
    string sourceSuite; /// Name of the suite packages migrate from
    string targetSuite; /// Name of the suite packages migrate to

    int[VersionPriority] delays;
    SpearsHint[] hints;
}

/**
 * Basic project configuration
 **/
struct SpearsConfig {
    SpearsConfigEntry[] migrations;
}

/**
 * List of old binaries of a specific version that a package has left behind.
 **/
struct SpearsOldBinaries {
    string pkgVersion;
    string[] binaries;
}

/**
 * Age requirements for a package to migrate
 **/
struct SpearsAgePolicy {
    long currentAge;
    long requiredAge;
}

/**
 * Reason why a package doesn't migrate
 **/
struct SpearsReason {
    string[] blockedBy; /// packages this package depends on which might prevent migration

    string[] migrateAfter;      /// packages queued to migrate before this one
    string[string] manualBlock; /// manual explicit block hints given by machines and people

    string[] other;    /// Other reasons for not migrating this package
    string logExcerpt; /// an excerpt from the migration log that is relevant to this package
}

/**
 * Information about missing builds
 **/
struct SpearsMissingBuilds {
    string[] primaryArchs;   /// primary architectures
    string[] secondaryArchs; /// secondary architectures
}

/**
 * Data for a package migration excuse, as emitted by Britney
 **/
class SpearsExcuse {
    mixin UUIDProperty;

    DateTime date;        /// Time when this excuse was created

    string sourceSuite;   /// Source suite of this package
    string targetSuite;   /// Target suite of this package

    bool isCandidate;     /// True if the package is considered for migration at all

    string sourcePackage; /// source package that is affected by this excuse
    string maintainer;    /// name of the maintainer responsible for this package

    SpearsAgePolicy age;  /// policy on how old the package needs to be to migrate
    mixin (JsonDatabaseField! ("age", "age", "SpearsAgePolicy"));

    string newVersion;    /// package version waiting to migrate
    string oldVersion;    /// old package version in the target suite

    SpearsMissingBuilds missingBuilds; /// list of architectures where the package has not been built
    mixin (JsonDatabaseField! ("missing_builds", "missingBuilds", "SpearsMissingBuilds"));

    SpearsOldBinaries[] oldBinaries; /// Superseded cruft binaries that need to be garbage-collected
    mixin (JsonDatabaseField!("old_binaries", "oldBinaries", "SpearsOldBinaries[]"));

    SpearsReason reason; /// reasoning on why this might not be allowed to migrate
    mixin (JsonDatabaseField! ("reason", "reason", "SpearsReason"));
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    auto schema = new SchemaInfoImpl! (SpearsExcuse);

    auto factory = db.newSessionFactory (schema);
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData().updateDBSchema (conn, false, true);

    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    // ensure we use the right datatypes - the ORM is not smart enough to
    // figure out the proper types
    stmt.executeUpdate (
        "ALTER TABLE spears_excuse
         ALTER COLUMN uuid TYPE UUID USING uuid::uuid,
         ALTER COLUMN age TYPE JSONB USING age::jsonb,
         ALTER COLUMN missing_builds TYPE JSONB USING missing_builds::jsonb,
         ALTER COLUMN old_binaries TYPE JSONB USING old_binaries::jsonb,
         ALTER COLUMN reason TYPE JSONB USING reason::jsonb;"
    );
}

/**
 * Add/update Spears configuration.
 */
void update (Database db, SpearsConfig conf)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.SPEARS, "migrations", conf.migrations);
}

auto getSpearsConfig (Database db)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    SpearsConfig conf;
    conf.migrations = db.getConfigEntry!(SpearsConfigEntry[]) (conn, LkModule.SPEARS, "migrations");

    return conf;
}

void removeSpearsExcusesForSuites (Connection conn, string sourceSuite, string targetSuite) @trusted
{
    auto ps = conn.prepareStatement ("DELETE FROM spears_excuse WHERE source_suite=$1 AND target_suite=$2");
    scope (exit) ps.close ();

    ps.setString (1, sourceSuite);
    ps.setString (2, targetSuite);

    ps.executeUpdate ();
}

long countSpearsExcusesForSuites (Connection conn, string sourceSuite, string targetSuite) @trusted
{
    auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM spears_excuse WHERE source_suite=$1 AND target_suite=$2");
    scope (exit) ps.close ();

    ps.setString (1, sourceSuite);
    ps.setString (2, targetSuite);

    Variant var;
    ps.executeUpdate (var);

    return var.get!long;
}
