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

import std.datetime : SysTime;
public import laniakea.pkgitems : PackageType;
import laniakea.db.lkid;
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
struct DebcheckIssue {
    LkId lkid;

    SysTime date;        /// Time when this excuse was created

    PackageType packageKind; /// Kind of the examined package
    string suiteName;
    string packageName;
    string packageVersion;
    string architecture;

    PackageIssue[] missing;
    PackageConflict[] conflicts;
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    conn.exec (
        "CREATE TABLE IF NOT EXISTS debcheck (
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
}

/**
 * Add/update basic configuration.
 */
void update (Database db, DebcheckIssue issue, bool isNew = false) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    if (isNew)
        issue.lkid = newLkid! (LkidType.DEBCHECK);

    QueryParams p;
    p.sqlCommand = "INSERT INTO debcheck
                    VALUES ($1,
                            to_timestamp($2),
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8::jsonb,
                            $9::jsonb)
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
