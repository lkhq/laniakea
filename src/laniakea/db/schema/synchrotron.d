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

module laniakea.db.schema.synchrotron;
@safe:

import std.datetime : DateTime;
import laniakea.db.schema.core;

/**
 * Information about a Synchrotron data source
 */
struct SyncSourceInfo {
    string defaultSuite;    // default suite name, e.g. "sid"
    DistroSuite[] suites;   // suites available in the source ("sid", "jessie", ...)

    string repoUrl;         // URL of the package repository
}

/**
 * Basic configuration for Synchrotron
 **/
struct SynchrotronConfig {
    string sourceName;     // Name of the source OS (usually "Debian")
    SyncSourceInfo source;

    bool syncEnabled;      // true if syncs should happen
    bool syncBinaries;     // true if we should also sync binary packages
}

/**
 * Synchrotron blacklist
 **/
struct SynchrotronBlacklist {
    string[string] blacklist; // array of blacklisted package (key) and blacklist reasons (value)
}

/**
 * Kind of a Synchrotron issue.
 **/
enum SynchrotronIssueKind {
    UNKNOWN,
    NONE,
    MERGE_REQUIRED,
    MAYBE_CRUFT,
    SYNC_FAILED,
    REMOVAL_FAILED
}

/**
 * Hints about why packages are not synchronized.
 **/
struct SynchrotronIssue {
    LkId lkid;

    DateTime date;              /// Time when this excuse was created

    SynchrotronIssueKind kind; /// Kind of this issue, and usually also the reason for it.

    string packageName; /// Name of the source package that is to be synchronized

    string sourceSuite;   /// Source suite of this package, usually the one in Debian
    string targetSuite;   /// Target suite of this package, from the target distribution

    string sourceVersion; /// package version to be synced
    string targetVersion; /// version of the package in the target suite and repo, to be overriden

    string details;  /// additional information text about the issue (usually a log excerpt)

    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &date,
                 &kind,
                 &packageName,
                 &sourceSuite,
                 &targetSuite,
                 &sourceVersion,
                 &targetVersion,
                 &details
        );
    }
}


import laniakea.db.database;

enum synchrotronIssuesTableName = "synchrotron_issues";

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    conn.exec (
        "CREATE TABLE IF NOT EXISTS " ~ synchrotronIssuesTableName ~ " (
          lkid VARCHAR(32) PRIMARY KEY,
          date             TIMESTAMP NOT NULL,
          kind             SMALLINT,
          package_name     TEXT NOT NULL,
          source_suite     TEXT NOT NULL,
          target_suite     TEXT NOT NULL,
          source_version   TEXT,
          target_version   TEXT,
          details          TEXT
        )"
    );
}

/**
 * Add/update Synchrotron issue.
 */
void update (PgConnection conn, SynchrotronIssue issue) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO " ~ synchrotronIssuesTableName ~ "
                    VALUES ($1,
                            to_timestamp($2),
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8,
                            $9
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      date            = to_timestamp($2),
                      kind            = $3,
                      package_name    = $4,
                      source_suite    = $5,
                      target_suite    = $6,
                      source_version  = $7,
                      target_version  = $8,
                      details         = $9";

    p.setParams (issue.lkid,
                 issue.date,
                 issue.kind,
                 issue.packageName,
                 issue.sourceSuite,
                 issue.targetSuite,
                 issue.sourceVersion,
                 issue.targetVersion,
                 issue.details

    );
    conn.execParams (p);
}

/**
 * Add/update Synchrotron configuration.
 */
void update (Database db, SynchrotronConfig conf)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.SYNCHROTRON, "sourceName", conf.sourceName);
    db.updateConfigEntry (conn, LkModule.SYNCHROTRON, "source", conf.source);
    db.updateConfigEntry (conn, LkModule.SYNCHROTRON, "syncEnabled", conf.syncEnabled);
    db.updateConfigEntry (conn, LkModule.SYNCHROTRON, "syncBinaries", conf.syncBinaries);
}

auto getSynchrotronConfig (Database db)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    SynchrotronConfig conf;
    conf.sourceName   = db.getConfigEntry!string (conn, LkModule.SYNCHROTRON, "sourceName");
    conf.source       = db.getConfigEntry!SyncSourceInfo (conn, LkModule.SYNCHROTRON, "source");
    conf.syncEnabled  = db.getConfigEntry!bool (conn, LkModule.SYNCHROTRON, "syncEnabled");
    conf.syncBinaries = db.getConfigEntry!bool (conn, LkModule.SYNCHROTRON, "syncBinaries");

    return conf;
}

/**
 * Add/update Synchrotron blacklist.
 */
void update (Database db, SynchrotronBlacklist blist)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.SYNCHROTRON, "blacklist", blist.blacklist);
}

auto getSynchrotronBlacklist (Database db)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    SynchrotronBlacklist blist;
    blist.blacklist = db.getConfigEntry!(string[string]) (conn, LkModule.SYNCHROTRON, "blacklist");

    return blist;
}

void removeSynchrotronIssuesForSuites (PgConnection conn, string sourceSuite, string targetSuite) @trusted
{
    QueryParams p;
    p.sqlCommand = "DELETE FROM " ~ synchrotronIssuesTableName ~ " WHERE source_suite=$1 AND target_suite=$2";
    p.setParams (sourceSuite, targetSuite);
    conn.execParams(p);
}

auto getSynchrotronIssues (PgConnection conn, long limit, long offset = 0) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM " ~ synchrotronIssuesTableName ~ " ORDER BY package_name LIMIT $1 OFFSET $2";
    if (limit > 0)
        p.setParams (limit, offset);
    else
        p.setParams (long.max, offset);

    auto ans = conn.execParams(p);
    return rowsTo!SynchrotronIssue (ans);
}
