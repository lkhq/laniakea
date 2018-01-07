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

import std.datetime : DateTime;
public import laniakea.pkgitems : PackageType;
import laniakea.db.utils;
import std.conv : to;
@safe:

/**
 * Information about the package issue reason.
 **/
struct PackageIssue {
    PackageType packageKind;
    string packageName;
    string packageVersion;
    string architecture;

    string depends;
    string unsatDependency;
    string unsatConflict;
}

/**
 * Information about the conflicting packages issue reason.
 */
struct PackageConflict {
    PackageIssue pkg1;
    PackageIssue pkg2;

    PackageIssue[] depchain1;
    PackageIssue[] depchain2;
}

/**
 * Dependency issue information
 **/
class DebcheckIssue {
    mixin UUIDProperty;

    DateTime date;           /// Time when this excuse was created

    PackageType packageKind; /// Kind of the examined package
    mixin (EnumDatabaseField!("package_kind", "packageKind", "PackageType", true));

    string suiteName;
    string packageName;
    string packageVersion;
    string architecture;

    PackageIssue[] missing;
    mixin (JsonDatabaseField!("missing", "missing", "PackageIssue[]"));

    PackageConflict[] conflicts;
    mixin (JsonDatabaseField!("conflicts", "conflicts", "PackageConflict[]"));
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    auto schema = new SchemaInfoImpl! (DebcheckIssue);

    auto factory = db.newSessionFactory (schema);
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData().updateDBSchema (conn, false, true);

    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    // ensure we use the right datatypes - the ORM is not smart enough to
    // figure out the proper types
    stmt.executeUpdate (
        "ALTER TABLE debcheck_issue
         ALTER COLUMN uuid TYPE UUID USING uuid::uuid,
         ALTER COLUMN missing TYPE JSONB USING missing::jsonb,
         ALTER COLUMN conflicts TYPE JSONB USING conflicts::jsonb;"
    );

    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS debcheck_issue_package_name_idx
                         ON debcheck_issue (package_name)");
}

void removeDebcheckIssues (Connection conn, string suiteName, PackageType pkind, string architecture = null) @trusted
{
    import std.array : empty;

    if (architecture.empty) {
        auto ps = conn.prepareStatement ("DELETE FROM debcheck_issue WHERE suite_name=$1 AND package_kind=$2");
        scope (exit) ps.close ();

        ps.setString (1, suiteName);
        ps.setShort (2, pkind.to!short);
        ps.executeUpdate ();
    } else {
        auto ps = conn.prepareStatement ("DELETE FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2 AND architecture=$3");
        scope (exit) ps.close ();

        ps.setString (1, suiteName);
        ps.setShort (2, pkind.to!short);
        ps.setString (3, architecture);
        ps.executeUpdate ();
    }
}

long countDebcheckIssues (Connection conn, string suiteName, PackageType pkind, string architecture = null) @trusted
{
    import std.array : empty;

    Variant var;
    if (architecture.empty) {
        auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM debcheck_issue WHERE suite_name=$1 AND package_kind=$2");
        scope (exit) ps.close ();

        ps.setString (1, suiteName);
        ps.setShort (2, pkind.to!short);
        ps.executeUpdate (var);
    } else {
        auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM debcheck_issue WHERE suite_name=$1 AND package_kind=$2 AND architecture=$3");
        scope (exit) ps.close ();

        ps.setString (1, suiteName);
        ps.setShort (2, pkind.to!short);
        ps.setString (3, architecture);
        ps.executeUpdate ();
    }

    return var.get!long;
}
