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

module lknative.config.jobs;
@safe:

import lknative.logging;
import lknative.config.core;
import std.uuid : randomUUID;
import std.conv : to;

public import vibe.data.json : Json;
public import std.datetime : DateTime;
public import std.uuid : UUID;

/**
 * State this job is in.
 **/
enum JobStatus
{
    UNKNOWN,
    WAITING,    /// waiting for someone to take the job
    DEPWAIT,    /// waiting for a dependency
    SCHEDULED,  /// job has been assigned,
    RUNNING,    /// the job is running
    DONE,       /// the job is done
    TERMINATED, /// the job was terminated
    STARVING    /// the job was denied computing resources for an extended period of time
}

/**
 * Result of a job.
 **/
enum JobResult
{
    UNKNOWN,
    SUCCESS_PENDING,     /// job was successful, but artifacts are still missing
    SUCCESS,             /// job was successful
    FAILURE_DEPENDENCY,  /// job was aborted because of a dependency issue
    FAILURE_PENDING,     /// job failed, but artifacts and reports are still missing
    FAILURE              /// job failed
}

/**
 * The different job kind identifier strings used by
 * the different Laniakea modules which can enqueue jobs.
 */
enum JobKind
{
    OS_IMAGE_BUILD = "os-image-build",
    PACKAGE_BUILD  = "package-build"
}

/**
 * A task pending to be performed.
 **/
struct Job
{
    import vibe.data.serialization : name;

    UUID uuid;

    JobStatus status; /// Status of this job

    @name("module")
    string moduleName; /// the name of the module responsible for this job
    string kind;       /// kind of the job

    UUID trigger;     /// ID of the entity responsible for triggering this job's creation
    string ver;       /// Version of the item this job is for (can be null)
    string architecture = "any"; /// Architecture this job can run on, "any" in case the architecture does not matter

    DateTime createdTime;  /// Time when this job was created.
    DateTime assignedTime; /// Time when this job was assigned to a worker.
    DateTime finishedTime; /// Time when this job was finished.
    int priority;          /// Priority of this job (higher value means faster execution of the task)

    UUID   workerId;       /// Unique ID of the entity the job is assigned to

    string latestLogExcerpt; /// An excerpt of the current job log

    JobResult result;

    Json data;
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
    UUID uuid;

    EventKind kind;    /// Type of this event
    string moduleName; /// the name of the module responsible for this event
    DateTime time;     /// Time when this issue was created.

    string title;      /// A human-readable title of this issue
    string text;       /// content of this issue
}
