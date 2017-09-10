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

module laniakea.db.basic;

import laniakea.db.database;

public import laniakea.db.schema : LkModule;

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

/**
 * Create initial tables for this module.
 */
void createTables (Database db)
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

    db.updateConfigEntry (conn, LkModule.BASE, "projectName", conf.projectName.serializeToJsonString);
    db.updateConfigEntry (conn, LkModule.BASE, "suites", conf.suites.serializeToJsonString);

    db.updateConfigEntry (conn, LkModule.BASE, "archive.develSuite", conf.archive.develSuite.serializeToJsonString);
    db.updateConfigEntry (conn, LkModule.BASE, "archive.incomingSuite", conf.archive.incomingSuite.serializeToJsonString);
    db.updateConfigEntry (conn, LkModule.BASE, "archive.distroTag", conf.archive.distroTag.serializeToJsonString);
}
