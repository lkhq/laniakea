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

module lknative.db.schema.spears;
@safe:

import std.uuid : UUID;
import std.datetime : DateTime;

import lknative.repository.types : VersionPriority;


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
    string[] sourceSuites; /// Names of the suites packages migrate from
    string targetSuite;    /// Name of the suite packages migrate to

    int[VersionPriority] delays;
    SpearsHint[] hints;

    /**
     * Get a string identifying the source suites packages are migrated from.
     */
    string sourceSuitesId ()
    {
        import std.algorithm : sort;
        import std.array : join;

        return sourceSuites.sort.join ("+");
    }

    /**
     * Get a unique identifier for this migration task
     */
    string migrationId ()
    {
        import std.string : format;

        return "%s-to-%s".format (this.sourceSuitesId, targetSuite);
    }
}

/**
 * Basic project configuration
 **/
struct SpearsConfig {
    SpearsConfigEntry[string] migrations;
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
    UUID uuid;

    DateTime date;        /// Time when this excuse was created

    string migrationId;   /// Identifier for the respective migration task, in the form of "source1+source2-to-target"

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
}
