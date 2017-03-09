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
