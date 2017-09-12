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

module laniakea.db.schema.jobs;
@safe:

import laniakea.logging;
import laniakea.db.schema.core;
public import std.datetime : DateTime;
public import laniakea.db.lkid : LkId, LkidType;

/**
 * State this job is in.
 **/
enum JobStatus
{
    UNKNOWN,
    WAITING,   /// waiting for someone to take the job
    SCHEDULED, /// job has been assigned,
    RUNNING,
    DONE,
    STARVING   /// the job was left abandoned for too long
}

/**
 * Result of a job.
 **/
enum JobResult
{
    UNKNOWN,
    SUCCESS,
    FAILURE,
    MAYBE_SUCCESS,
    MAYBE_FAILURE
}

/**
 * A task pending to be performed.
 **/
template Job(LkModule mod, string jobKind) {
    LkId lkid;

    JobStatus status; /// Status of this job

    string moduleName = mod; /// the name of the module responsible for this job
    string kind = jobKind;  /// kind of the job

    string title;     /// A human-readable title of this job

    LkId trigger = "";     /// ID of the entity responsible for triggering this job's creation

    DateTime createdTime;  /// Time when this job was created.
    DateTime assignedTime; /// Time when this job was assigned to a worker.
    DateTime finishedTime; /// Time when this job was finished.

    string worker;        /// The person/system/tool this job is assigned to
    LkId   workerId = ""; /// Unique ID of the entity the job is assigned to

    string latestLogExcerpt;   /// An excerpt of the current job log

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
    LkId lkid;

    EventKind kind;     // Type of this event
    string moduleName; // the name of the module responsible for this event
    DateTime time;  // Time when this issue was created.

    string title;     // A human-readable title of this issue
    string content;   // content of this issue
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
        "CREATE TABLE IF NOT EXISTS jobs (
          lkid VARCHAR(32) PRIMARY KEY,
          status           SMALLINT,
          module           TEXT NOT NULL,
          kind             TEXT NOT NULL,
          title            TEXT,
          trigger          VARCHAR(32),
          time_created     TIMESTAMP NOT NULL,
          time_assigned    TIMESTAMP NOT NULL,
          time_finished    TIMESTAMP NOT NULL,
          worker_name      TEXT,
          worker_id        VARCHAR(32),
          result           SMALLINT,
          latest_log_excerpt TEXT NOT NULL,
          data             JSONB
        )"
    );
}

/**
 * Add/update a job.
 */
void updateJob (T) (Database db, T job) @trusted
{
    import std.traits : hasMember;
    static assert (hasMember!(T, "lkid"));
    static assert (hasMember!(T, "status"));
    static assert (hasMember!(T, "result"));

    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    QueryParams p;
    p.sqlCommand = "INSERT INTO jobs
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            to_timestamp($7),
                            to_timestamp($8),
                            to_timestamp($9),
                            $10,
                            $11,
                            $12,
                            $13,
                            $14::jsonb
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      status           = $2,
                      module           = $3,
                      kind             = $4,
                      title            = $5,
                      trigger          = $6,
                      time_assigned    = to_timestamp($8),
                      time_finished    = to_timestamp($9),
                      worker_name      = $10,
                      worker_id        = $11,
                      result           = $12,
                      latest_log_excerpt = $13,
                      data             = $14::jsonb";

    static if (hasMember!(T, "data"))
        auto data = job.data;
    else
        auto data = "";

    p.setParams (job.lkid,
                 job.status,
                 job.moduleName,
                 job.kind,
                 job.title,
                 job.trigger,
                 job.createdTime,
                 job.assignedTime,
                 job.finishedTime,
                 job.worker,
                 job.workerId,
                 job.result,
                 job.latestLogExcerpt,
                 data
    );

    conn.execParams (p);
}

/**
 * Add a new job to the database.
 */
void addJob (J) (Database db, J job, LkId trigger)
{
    import laniakea.db.lkid : generateNewLkid;
    import laniakea.utils : currentDateTime;
    import std.array : empty;
    import std.string : format;

    job.lkid = generateNewLkid! (LkidType.JOB);
    job.createdTime = currentDateTime;
    job.status = JobStatus.WAITING;
    job.trigger = trigger;

    // set a dummy titke for displaying information in UIs which do not
    // have knowledge of all Laniakea modules
    if (job.title.empty) {
        job.title = "%s %s job".format (job.moduleName, job.kind);
    }

    logInfo ("Adding job '%s'", job.lkid);
    db.updateJob (job);
}
