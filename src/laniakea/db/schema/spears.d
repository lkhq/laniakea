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

import laniakea.db.schema.core;
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

    uint[VersionPriority] delays;
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
    uint currentAge;
    uint requiredAge;
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
struct SpearsExcuse {
    LkId lkid;

    DateTime date;        /// Time when this excuse was created

    string sourceSuite;   /// Source suite of this package
    string targetSuite;   /// Target suite of this package

    bool isCandidate;     /// True if the package is considered for migration at all

    string sourcePackage; /// source package that is affected by this excuse
    string maintainer;    /// name of the maintainer responsible for this package

    SpearsAgePolicy age;  /// policy on how old the package needs to be to migrate

    string newVersion;    /// package version waiting to migrate
    string oldVersion;    /// old package version in the target suite

    SpearsMissingBuilds missingBuilds; /// list of architectures where the package has not been built

    SpearsOldBinaries[] oldBinaries; /// Superseded cruft binaries that need to be garbage-collected

    SpearsReason reason; /// reasoning on why this might not be allowed to migrate

    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &date,
                 &sourceSuite,
                 &targetSuite,
                 &isCandidate,
                 &sourcePackage,
                 &maintainer,
                 &age,
                 &newVersion,
                 &oldVersion,
                 &missingBuilds,
                 &oldBinaries,
                 &reason
        );
    }
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    conn.exec (
        "CREATE TABLE IF NOT EXISTS spears_excuses (
          lkid VARCHAR(32) PRIMARY KEY,
          date             TIMESTAMP NOT NULL,
          source_suite     TEXT NOT NULL,
          target_suite     TEXT NOT NULL,
          candidate        BOOLEAN,
          source_package   TEXT NOT NULL,
          maintainer       TEXT,
          age              JSONB,
          version_new      TEXT NOT NULL,
          version_old      TEXT NOT NULL,
          missing_builds   JSONB,
          old_binaries     JSONB,
          reason           JSONB
        )"
    );
}

/**
 * Add/update Spears excuse.
 */
void update (PgConnection conn, SpearsExcuse excuse) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO spears_excuses
                    VALUES ($1,
                            to_timestamp($2),
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8::jsonb,
                            $9,
                            $10,
                            $11::jsonb,
                            $12::jsonb,
                            $13::jsonb
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      date            = to_timestamp($2),
                      source_suite    = $3,
                      target_suite    = $4,
                      candidate       = $5,
                      source_package  = $6,
                      maintainer      = $7,
                      age             = $8::jsonb,
                      version_new     = $9,
                      version_old     = $10,
                      missing_builds  = $11::jsonb,
                      old_binaries    = $12::jsonb,
                      reason          = $13::jsonb";

    p.setParams (excuse.lkid,
                 excuse.date,
                 excuse.sourceSuite,
                 excuse.targetSuite,
                 excuse.isCandidate,
                 excuse.sourcePackage,
                 excuse.maintainer,
                 excuse.age,
                 excuse.newVersion,
                 excuse.oldVersion,
                 excuse.missingBuilds,
                 excuse.oldBinaries,
                 excuse.reason

    );
    conn.execParams (p);
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
    conf.migrations = db.getConfigEntry!(SpearsConfigEntry[]) (conn, LkModule.BASE, "migrations");

    return conf;
}

void removeSpearsExcusesForSuites (PgConnection conn, string sourceSuite, string targetSuite) @trusted
{
    QueryParams p;

    p.sqlCommand = "DELETE FROM spears_excuses WHERE source_suite=$1 AND target_suite=$2";
    p.setParams (sourceSuite, targetSuite);
    conn.execParams(p);
}
