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

module laniakea.db.schema.debcheck;
@safe:

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;

enum PackageKind {
    SOURCE,
    BINARY
}

/**
 * Information about the package issue reason.
 **/
struct PackageInfo {
    string packageName;
    string packageVersion;
    PackageKind packageKind;

    string depends;
    string unsatDependency;
    string unsatConflict;
}

/**
 * Information about the conflicting packages issue reason.
 */
struct ConflictInfo {
    PackageInfo pkg1;
    PackageInfo pkg2;

    PackageInfo[] depchain1;
    PackageInfo[] depchain2;
}

/**
 * Dependency issue information
 **/
struct DebcheckIssue {
    @name("_id") BsonObjectID id;

    BsonDate date;        /// Time when this excuse was created

    PackageKind packageKind; /// Kind of the examined package

    string packageName;
    string packageVersion;
    string architecture;

    PackageInfo[] missing;
    ConflictInfo[] conflict;
}
