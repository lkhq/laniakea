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

 import vibe.db.mongo.mongo;
 import vibe.data.serialization : name;
 import laniakea.db.schema.basic;

/**
 * Configuration kind.
 **/
enum SynchrotronConfigKind {
    UNKNOWN,
    BASE,
    BLACKLIST
}

/**
 * Information about a Synchrotron data source
 */
struct SyncSourceInfo {
    string defaultSuite;    // default suite name, e.g. "sid"
    string[] architectures; // architectures of the source suite
    DistroSuite[] suites;   // suites available in the source ("sid", "jessie", ...)

    string repoUrl;         // URL of the package repository
}

/**
 * Basic configuration for Synchrotron
 **/
struct SynchrotronConfig {
    @name("_id") BsonObjectID id;

    SynchrotronConfigKind kind = SynchrotronConfigKind.BASE;
    string sourceName;     // Name of the source OS (usually "Debian")
    SyncSourceInfo source;

    bool syncEnabled;      // true if syncs should happen
    bool syncBinaries;     // true if we should also sync binary packages
}

/**
 * Synchrotron blacklist
 **/
struct SynchrotronBlacklist {
    @name("_id") BsonObjectID id;

    SynchrotronConfigKind kind = SynchrotronConfigKind.BLACKLIST;
    string[] blacklist;
}
