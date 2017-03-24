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

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;

import laniakea.pkgitems : VersionPriority;

/**
 * Spears configuration kind
 **/
enum SpearsConfigKind {
    UNKNOWN,
    BASE
}

/**
 * Configuration specific for the spears tool.
 */
struct SpearsConfigEntry
{
    string fromSuite;
    string toSuite;

    uint[VersionPriority] delays;
}

/**
 * Basic project configuration
 **/
struct SpearsConfig {
    @name("_id") BsonObjectID id;

    SpearsConfigKind kind = SpearsConfigKind.BASE;

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

    string[] migrateAfter; /// packages queued to migrate before this one
    string[string] manualBlock;  /// manual explicit block hints given by machines and people
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
    @name("_id") BsonObjectID id;

    string sourceSuite;   /// Source suite of this package
    string targetSuite;   /// Target suite of this package

    string sourcePackage; /// source package that is affected by this excuse
    string maintainer;    /// name of the maintainer responsible for this package

    SpearsAgePolicy age;  /// policy on how old the package needs to be to migrate

    string newVersion;    /// package version waiting to migrate
    string oldVersion;    /// old package version in the target suite

    SpearsMissingBuilds missingBuilds; /// list of architectures where the package has not been built

    SpearsOldBinaries[] oldBinaries; /// Superseded cruft binaries that need to be garbage-collected

    SpearsReason reason; /// reasoning on why this might not be allowed to migrate

    bool isCandidate;
}
