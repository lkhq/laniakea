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

module lknative.config.synchrotron;
@safe:

import std.uuid : UUID;
import std.datetime : DateTime;


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
class SyncBlacklistEntry {
    string pkgname; /// Name of the blacklisted package
    DateTime date;  /// Time when the package was blacklisted
    string reason;  /// Reason why the package is blacklisted
    string user;    /// Person who marked this to be ignored
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
    UUID uuid;

    DateTime date;              /// Time when this excuse was created

    SynchrotronIssueKind kind; /// Kind of this issue, and usually also the reason for it.

    string packageName; /// Name of the source package that is to be synchronized

    string sourceSuite;   /// Source suite of this package, usually the one in Debian
    string targetSuite;   /// Target suite of this package, from the target distribution

    string sourceVersion; /// package version to be synced
    string targetVersion; /// version of the package in the target suite and repo, to be overriden

    string details;  /// additional information text about the issue (usually a log excerpt)
}
