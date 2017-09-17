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

    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &status,
                 &moduleName,
                 &kind,
                 &title,
                 &trigger,
                 &createdTime,
                 &assignedTime,
                 &finishedTime,
                 &worker,
                 &workerId,
                 &result,
                 &latestLogExcerpt,
                 &data
        );
    }
}

/**
 * A generic job type.
 */
struct GenericJob {
    mixin Job!(LkModule.UNKNOWN, "generic");

    Bson data;
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

    EventKind kind;    /// Type of this event
    string moduleName; /// the name of the module responsible for this event
    DateTime time;     /// Time when this issue was created.

    string title;      /// A human-readable title of this issue
    string text;       /// content of this issue

    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &kind,
                 &moduleName,
                 &time,
                 &title,
                 &text
        );
    }
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    // Jobs table
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
          latest_log_excerpt TEXT,
          data             JSONB
        )"
    );

    // Events table
    conn.exec (
        "CREATE TABLE IF NOT EXISTS events (
          lkid VARCHAR(32) PRIMARY KEY,
          kind             SMALLINT,
          module           TEXT NOT NULL,
          time             TIMESTAMP NOT NULL,
          title            TEXT NOT NULL,
          text             TEXT
        )"
    );
}

/**
 * Add/update a job.
 */
void updateJob (T) (PgConnection conn, T job) @trusted
{
    import std.traits : hasMember;
    static assert (hasMember!(T, "lkid"));
    static assert (hasMember!(T, "status"));
    static assert (hasMember!(T, "result"));

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
        auto data = "{}";

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
void addJob (J) (PgConnection conn, J job, LkId trigger)
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
    conn.updateJob (job);
}

/**
 * Find jobs of type T by their trigger ID.
 */
auto getJobsByTrigger (T) (PgConnection conn, LkId triggerId, long limit, long offset = 0) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM jobs WHERE trigger=$1 ORDER BY time_created DESC LIMIT $2 OFFSET $3";
    if (limit > 0)
        p.setParams (triggerId, limit, offset);
    else
        p.setParams (triggerId, long.max, offset);

    auto ans = conn.execParams(p);
    return rowsTo!T (ans);
}

/**
 * Find a job by its Laniakea ID, return it as raw SQL answer.
 */
auto getRawJobById (PgConnection conn, LkId lkid) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM jobs WHERE lkid=$1";
    p.setParams (lkid);
    auto ans = conn.execParams(p);

    if (ans.length > 0)
        return ans[0];
    else
        return PgRow();
}

/**
 * Get the responsible module from a raw job SQL row.
 */
auto rawJobGetModule (PgRow r) @trusted
{
    if (r.length < 14)
        return null;
    return r[2].dbValueTo!LkModule;
}

/**
 * Change result of job.
 */
auto setJobResult (T) (PgConnection conn, LkId jobId, JobResult result) @trusted
{
    QueryParams p;
    p.sqlCommand = "UPDATE jobs SET result=$1 WHERE lkid=$2 RETURNING *";
    p.setParams (result, jobId);

    auto ans = conn.execParams (p);
    return rowsToOne!T (ans);
}

/**
 * Change status of job.
 */
bool setJobStatus (PgConnection conn, LkId jobId, JobStatus status) @trusted
{
    QueryParams p;
    p.sqlCommand = "UPDATE jobs SET status=$1 WHERE lkid=$2";
    p.setParams (status, jobId);

    conn.execParams (p);
    return true;
}

/**
 * Set the latest log excerpt
 */
bool setJobLogExcerpt (PgConnection conn, LkId jobId, string excerpt) @trusted
{
    QueryParams p;
    p.sqlCommand = "UPDATE jobs SET latest_log_excerpt=$1 WHERE lkid=$2";
    p.setParams (excerpt, jobId);
    conn.execParams (p);
    return true;
}

/**
 * Add a new event to the database (using a DB connection)
 */
void addEvent (PgConnection conn, EventKind kind, string title, string text) @trusted
{
    import laniakea.db.lkid;
    import laniakea.localconfig : LocalConfig;
    const conf = LocalConfig.get;

    QueryParams p;
    p.sqlCommand = "INSERT INTO events
                    VALUES ($1,
                            $2,
                            $3,
                            now(),
                            $4,
                            $5
                        )";

    p.setParams (generateNewLkid! (LkidType.EVENT),
                 kind,
                 conf.currentModule,
                 title,
                 text
    );
    conn.execParams (p);
}

/**
 * Add a new event (creating a new temporary connection)
 */
void addEvent (Database db, EventKind kind, string title, string text) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);
    addEvent (conn, kind, title, text);
}