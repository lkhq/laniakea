/*
 * Copyright (C) 2016 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.db.schema.basic;
@safe:

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;

/**
 * A list of all modules integrated into the Laniakea suite,
 * with their respective identifier strings.
 * Any piece that uses the database *requires* a module name.
 */
enum LkModule
{
    UNKNOWN     = "",
    BASE        = "base",        /// The Laniakea base platform
    LIGHTHOUSE  = "lighthouse",  /// Message relay station
    SYNCHROTRON = "synchrotron", /// Syncs packages from a source distribution
    SPEARS      = "spears",      /// Automatic package migration
    EGGSHELL    = "eggshell",    /// Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI    = "admin-cli",   /// CLI interface to Laniakea settings and the database, useful debug tool
    KEYTOOL     = "keytool",     /// Small CLI tool to handle encryption keys and certificates
    WEB         = "web",         /// Laniakea web view
    DEBCHECK    = "debcheck",    /// Package installability and dependency tests
    ISOTOPE     = "isotope"      /// ISO image build scheduling and data import
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
    string develSuite;     // Development target suite ("testing", "green", ...)
    string incomingSuite;  // Suite where new packages typically arrive ("unstable", "staging", ...)
    string distroTag;      // Version tag for this distribution ("pureos", "tanglu", ...) - will usually be part of a package version, e.g. "1.0-0tanglu1"
}

/**
 * Basic project configuration
 **/
struct BaseConfig {
    @name("_id") BsonObjectID id;

    @name("module") string moduleName = LkModule.BASE;
    string kind = BaseConfig.stringof;

    string projectName;         // Name of the distrobution or project ("Tanglu", "PureOS", ...)
    BaseArchiveConfig archive;  // archive specific settings
    DistroSuite[] suites;       // suites this OS contains
}
