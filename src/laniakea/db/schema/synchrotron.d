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
import laniakea.db.utils;


/**
 * Information about a distribution suite the we can sync data from
 */
struct SyncSourceSuite
{
    string name;
    string[] architectures;
    string[] components;
}

/**
 * Information about a Synchrotron data source
 */
struct SyncSourceInfo {
    string defaultSuite;    // default suite name, e.g. "sid"
    SyncSourceSuite[] suites;   // suites available in the source ("sid", "jessie", ...)

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
@Table ("synchrotron_blacklist")
class SyncBlacklistEntry {
    @Id @UniqueKey
    string pkgname; /// Name of the blacklisted package
    DateTime date;  /// Time when the package was blacklisted
    string reason;  /// Reason why the package is blacklisted
    @Null string user;    /// Person who marked this to be ignored
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
class SynchrotronIssue {
    mixin UUIDProperty;

    DateTime date;              /// Time when this excuse was created

    SynchrotronIssueKind kind; /// Kind of this issue, and usually also the reason for it.
    mixin (EnumDatabaseField!("kind", "kind", "SynchrotronIssueKind", true));

    string packageName; /// Name of the source package that is to be synchronized

    string sourceSuite;   /// Source suite of this package, usually the one in Debian
    string targetSuite;   /// Target suite of this package, from the target distribution

    string sourceVersion; /// package version to be synced
    string targetVersion; /// version of the package in the target suite and repo, to be overriden

    string details;  /// additional information text about the issue (usually a log excerpt)
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    auto factory = db.newSessionFactory! (SyncBlacklistEntry,
                                          SynchrotronIssue);
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData().updateDBSchema (conn, false, true);

    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    // ensure we use the right datatypes - the ORM is not smart enough to
    // figure out the proper types
    stmt.executeUpdate (
        "ALTER TABLE synchrotron_issue
         ALTER COLUMN uuid TYPE UUID USING uuid::uuid;"
    );
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

void removeSynchrotronIssuesForSuites (Connection conn, string sourceSuite, string targetSuite) @trusted
{
    auto ps = conn.prepareStatement ("DELETE FROM synchrotron_issue WHERE source_suite=? AND target_suite=?");
    scope (exit) ps.close ();

    ps.setString (1, sourceSuite);
    ps.setString (2, targetSuite);

    ps.executeUpdate ();
}

auto getSynchrotronIssues (Session session, long limit, long offset = 0) @trusted
{
    if (limit <= 0)
        limit = long.max;

    auto q = session.createQuery ("FROM synchrontron_issue ORDER BY package_name LIMIT :lim OFFSET :offs")
                    .setParameter ("lim", limit).setParameter ("offs", offset);
    SynchrotronIssue[] list = q.list!SynchrotronIssue();

    return list;
}
