/*
 * Copyright (C) 2017-2018 Matthias Klumpp <matthias@tenstral.net>
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


// public imports with generaly useful stuff
public import std.array : empty;
public import std.uuid : UUID;
public import hibernated.annotations;


/**
 * A template to mix into classes containing a uuid primary key.
 **/
template UUIDProperty() {
    UUID uuid;
    @property @Column ("uuid") @Id @UniqueKey string uuid_s () { return uuid.toString; }
    @property void uuid_s (string s) { uuid = UUID (s); }
}

/**
 * A template to quickly add JSON/JSONB properties to database entities,
 * so Hibernated can recognize and serialize them.
 */
template JsonDatabaseField (string column, string fieldName, string dataType) {
    const char[] JsonDatabaseField =
        `@property @Column ("` ~ column ~ `")
         string ` ~ fieldName ~ `_json () {
             import vibe.data.json : serializeToJsonString;
             return serializeToJsonString (` ~ fieldName ~ `);
         };

         @property @Column ("` ~ column ~ `")
         void ` ~ fieldName ~ `_json (string v) {
             import vibe.data.json : deserializeJson;
             ` ~ fieldName ~ ` = v.deserializeJson! (` ~ dataType ~ `);
         };`;
}

/**
 * A template to make enums readable as integers for the Hibernated ORM.
 */
template EnumDatabaseField (string column, string fieldName, string dataType, bool isShort = false) {
    static if (isShort) {
        const char[] EnumDatabaseField =
            `@property @Column ("` ~ column ~ `")
            short ` ~ fieldName ~ `_i () {
                import std.conv : to;
                return ` ~ fieldName ~ `.to!short;
            };

            @property @Column ("` ~ column ~ `")
            void ` ~ fieldName ~ `_i (short v) {
                import std.conv : to;
                ` ~ fieldName ~ ` = v.to! (` ~ dataType ~ `);
            };`;
    } else {
        const char[] EnumDatabaseField =
            `@property @Column ("` ~ column ~ `")
            int ` ~ fieldName ~ `_i () {
                import std.conv : to;
                return ` ~ fieldName ~ `.to!int;
            };

            @property @Column ("` ~ column ~ `")
            void ` ~ fieldName ~ `_i (int v) {
                import std.conv : to;
                ` ~ fieldName ~ ` = v.to! (` ~ dataType ~ `);
            };`;
    }
}

