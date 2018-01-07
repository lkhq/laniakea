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


version(none) {

import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    conn.exec (
        "CREATE TABLE IF NOT EXISTS debcheck_issues (
          lkid VARCHAR(32) PRIMARY KEY,
          date             TIMESTAMP NOT NULL,
          package_kind     SMALLINT,
          suite_name       TEXT NOT NULL,
          package_name     TEXT NOT NULL,
          package_version  TEXT NOT NULL,
          architecture     TEXT NOT NULL,
          missing          JSONB,
          conflicts        JSONB
        )"
    );
    conn.exec ("CREATE INDEX IF NOT EXISTS debcheck_issues_package_name_idx
                ON debcheck_issues (package_name)");
}

/**
 * Add/update basic configuration.
 */
void update (PgConnection conn, DebcheckIssue issue, bool isNew = false) @trusted
{
    if (isNew)
        issue.lkid = generateNewLkid! (LkidType.DEBCHECK);

    QueryParams p;
    p.sqlCommand = "INSERT INTO debcheck_issues
                    VALUES ($1,
                            to_timestamp($2),
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8::jsonb,
                            $9::jsonb
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      date            = to_timestamp($2),
                      package_kind    = $3,
                      suite_name      = $4,
                      package_name    = $5,
                      package_version = $6,
                      architecture    = $7,
                      missing         = $8::jsonb,
                      conflicts       = $9::jsonb";

    p.setParams (issue.lkid,
                 issue.date,
                 issue.packageKind,
                 issue.suiteName,
                 issue.packageName,
                 issue.packageVersion,
                 issue.architecture,
                 issue.missing,
                 issue.conflicts
    );
    conn.execParams (p);
}

void removeDebcheckIssues (PgConnection conn, string suiteName, PackageType pkind, string architecture = null) @trusted
{
    import std.array : empty;
    QueryParams p;

    if (architecture.empty) {
        p.sqlCommand = "DELETE FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2";
        p.setParams (suiteName, pkind);
    } else {
        p.sqlCommand = "DELETE FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2 AND architecture=$3";
        p.setParams (suiteName, pkind, architecture);
    }

    conn.execParams(p);
}

auto getDebcheckIssues (PgConnection conn, string suiteName, PackageType pkind, string architecture = null, long limit = 0, long offset = 0) @trusted
{
    import std.array : empty;
    QueryParams p;

    if (architecture.empty) {
        p.sqlCommand = "SELECT * FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2 ORDER BY date LIMIT $3 OFFSET $4";
        if (limit == 0)
            p.setParams (suiteName, pkind, long.max, offset);
        else
            p.setParams (suiteName, pkind, limit, offset);
    } else {
        p.sqlCommand = "SELECT * FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2 AND architecture=$3 ORDER BY date LIMIT $4 OFFSET $5";
        if (limit == 0)
            p.setParams (suiteName, pkind, architecture, long.max, offset);
        else
            p.setParams (suiteName, pkind, architecture, limit, offset);
    }

    auto ans = conn.execParams(p);
    return rowsTo!DebcheckIssue (ans);
}

long countDebcheckIssues (PgConnection conn, string suiteName, PackageType pkind, string architecture = null) @trusted
{
    import std.array : empty;
    QueryParams p;

    if (architecture.empty) {
        p.sqlCommand = "SELECT COUNT(*) FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2";
        p.setParams (suiteName, pkind);
    } else {
        p.sqlCommand = "SELECT COUNT(*) FROM debcheck_issues WHERE suite_name=$1 AND package_kind=$2 AND architecture=$3";
        p.setParams (suiteName, pkind, architecture);
    }

    auto ans = conn.execParams(p);
    if (ans.length > 0) {
        const r = ans[0];
        if (r.length > 0)
            return r[0].dbValueTo!long;
    }
    return 0;
}

auto getDebcheckIssue (PgConnection conn, string suiteName, PackageType pkind, string packageName, string packageVersion) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM debcheck_issues WHERE
                    suite_name=$1 AND
                    package_kind=$2 AND
                    package_name=$3 AND
                    package_version=$4";
    p.setParams (suiteName, pkind, packageName, packageVersion);

    auto ans = conn.execParams(p);
    return rowsToOne!DebcheckIssue (ans);
}

}
