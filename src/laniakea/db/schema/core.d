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
    EGGSHELL    = "eggshell",    /// Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI    = "admin-cli",   /// CLI interface to Laniakea settings and the database, useful debug tool
    KEYTOOL     = "keytool",     /// Small CLI tool to handle encryption keys and certificates
    WEB         = "web",         /// Laniakea web view
    WEBSWVIEW   = "webswview",   /// Packages / software web view
    DEBCHECK    = "debcheck",    /// Package installability and dependency tests
    ISOTOPE     = "isotope",     /// ISO image build scheduling and data import
    RUBICON     = "rubicon",     /// Accepts job result artifacts (logfiles, built files, ...), verifies them and moves them to the right place
    ARCHIVE     = "archive",     /// Lists packages in the database
    DATASYNC    = "datasync"     /// Import various data from other sources into the database
}

/**
 * Information about a distribution component.
 */
struct DistroComponent
{
    string name;
    string[] dependencies;
}

/**
 * Information about a distribution suite.
 */
struct DistroSuite
{
    string name;
    string[] architectures;
    DistroComponent[] components;
    string baseSuiteName;
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
    DistroSuite[] suites;       /// suites this OS contains
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
        "CREATE TABLE IF NOT EXISTS config (
          id text PRIMARY KEY,
          data jsonb NOT NULL
        )"
    );
}

/**
 * Add/update basic configuration.
 */
void update (Database db, BaseConfig conf)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.BASE, "projectName", conf.projectName);
    db.updateConfigEntry (conn, LkModule.BASE, "suites", conf.suites);

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
    conf.suites = db.getConfigEntry!(DistroSuite[]) (conn, LkModule.BASE, "suites");
    conf.archive.develSuite = db.getConfigEntry!string (conn, LkModule.BASE, "archive.develSuite");
    conf.archive.incomingSuite = db.getConfigEntry!string (conn, LkModule.BASE, "archive.incomingSuite");
    conf.archive.distroTag = db.getConfigEntry!string (conn, LkModule.BASE, "archive.distroTag");

    return conf;
}

auto getSuite (Database db, string name)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    Nullable!DistroSuite suite;
    foreach (ref s; db.getConfigEntry!(DistroSuite[]) (conn, LkModule.BASE, "suites")) {
        if (s.name == name) {
            suite = s;
            break;
        }
    }
    return suite;
}
