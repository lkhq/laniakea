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

module laniakea.db.schema.basic;
@safe:

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;

/**
 * A list of all modules integrated into the Laniakea suite,
 * with their respective identifier strings.
 * Any piece that uses the database *requires* a module name.
 */
enum LkModule
{
    UNKNOWN     = "",
    BASE        = "base",        /// The Laniakea base platform
    SYNCHROTRON = "synchrotron", /// Syncs packages from a source distribution
    SPEARS      = "spears",      /// Automatic package migration
    EGGSHELL    = "eggshell",    /// Interface to Germinate, a metapackage / default-package-selection generator
    ADMINCLI    = "admin-cli",   /// CLI interface to Laniakea settings and the database, useful debug tool
    WEB         = "web"          /// Laniakea web view
}

/**
 * Type of the particular job.
 **/
enum JobMode
{
    UNKNOWN,
    ONESHOT,
    PERIODIC
}

/**
 * State this job is in.
 **/
enum JobStatus
{
    UNKNOWN,
    WAITING,   // waiting for someone to take the job
    SCHEDULED, // job has been assigned,
    RUNNING,
    DONE,
    STARVING   // the job was left abandoned for too long
}

/**
 * Result of a job.
 **/
enum JobResult
{
    UNKNOWN,
    SUCCESS,
    FAILURE
}

/**
 * A task pending to be performed.
 **/
struct Job {
    @name("_id") BsonObjectID id;

    JobMode mode;     // Type of the job
    JobStatus status; // Status of this job

    @name("module") string moduleName; // the name of the module responsible for this job
    string kind; // kind of the job

    string title;     // A human-readable title of this job

    string trigger;      // System responsible for triggering this job's creation
    string reason;       // Reson for this job's creation
    BsonDate createdTime;  // Time when this job was created.
    BsonDate finishedTime; // Time when this job was finished.

    string worker;  // The person/system/tool this job is assigned to
    string data;    // Machine-readable information for the system taking the job

    JobResult result;
}

/**
 * Type of an incident.
 **/
enum EventKind
{
    UNKNOWN,
    INFO,
    WARNING,
    ERROR,
    CRITICAL
}

/**
 * An event log entry.
 **/
struct EventEntry {
    @name("_id") BsonObjectID id;

    EventKind kind;     // Type of this event
    @name("module") string moduleName; // the name of the module responsible for this event
    BsonDate time;  // Time when this issue was created.

    string title;     // A human-readable title of this issue
    string content;   // content of this issue
}

/**
 * Information about a distribution suite.
 */
struct DistroSuite
{
    string name;
    string[] architectures;
    string[] components;
}

/**
 * Base configuration kind
 **/
enum BaseConfigKind {
    UNKNOWN,
    PROJECT
}

/**
 * Basic archive configuration
 **/
struct BaseArchiveConfig {
    string develSuite;     // Development target suite ("testing", "green", ...)
    string incomingSuite;  // Suite where new packages typically arrive ("unstable", "staging", ...)
    string distroTag;      // Version tag for this distribution ("pureos", "tanglu", ...) - will usually be part of a package version, e.g. "1.0-0tanglu1"
}

/**
 * Basic project configuration
 **/
struct BaseConfig {
    @name("_id") BsonObjectID id;

    BaseConfigKind kind = BaseConfigKind.PROJECT;

    string projectName;         // Name of the distrobution or project ("Tanglu", "PureOS", ...)
    BaseArchiveConfig archive;  // archive specific settings
    DistroSuite[] suites;       // suites this OS contains
}
