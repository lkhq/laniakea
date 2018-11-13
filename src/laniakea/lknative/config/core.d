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

module lknative.config.core;
@safe:

public immutable laniakeaVersion = "0.1";

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
    DATAIMPORT  = "dataimport",  /// Import various data from other sources into the database
    ARIADNE     = "ariadne"      /// Package autobuild scheduler
}

/**
 * Suite information
 */
struct SuiteInfo {
    string name;
    string[] architectures;
    string[] components;
}

/**
 * Basic archive configuration
 **/
struct BaseArchiveConfig {
    string develSuite;     /// Development target suite ("testing", "green", ...)
    string distroTag;      /// Version tag for this distribution ("pureos", "tanglu", ...) - will usually be part of a package version, e.g. "1.0-0tanglu1"
    string rootPath;       /// Repository root directory
    SuiteInfo incomingSuite;  /// Suite where new packages typically arrive ("unstable", "staging", ...)
}

/**
 * Basic project configuration
 **/
struct BaseConfig {
    string projectName;         /// Name of the distrobution or project ("Tanglu", "PureOS", ...)

    string cacheDir;            /// Location of caches
    string workspace;           /// Persistent workspace to store data

    BaseArchiveConfig archive;  /// archive specific settings
}
