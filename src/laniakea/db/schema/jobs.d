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

module laniakea.db.schema.jobs;
@safe:

import laniakea.logging;
import laniakea.db.schema.core;
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
    WAITING,   /// waiting for someone to take the job
    SCHEDULED, /// job has been assigned,
    RUNNING,
    DONE,
    TERMINATED, /// the job was terminated
    STARVING    /// the job was denied computing resources for an extended period of time
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
 * The different job kind identifier strings used by
 * the different Laniakea modules which can enqueue jobs.
 */
enum JobKind
{
    OS_IMAGE_BUILD = "iso-image-build",
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

    this (ResultSet r) @trusted
    {
        import std.conv : to;
        import vibe.data.json : parseJsonString;
        import laniakea.utils : safeParseUUID;
        assert (r.getMetaData.getColumnCount == 15);

        uuid         = safeParseUUID (r.getString (1));
        status       = r.getShort (2).to!JobStatus;
        moduleName   = r.getString (3);
        kind         = r.getString (4);
        trigger      = safeParseUUID (r.getString (5));
        ver          = r.getString (6);
        architecture = r.getString (7);

        createdTime  = r.getDateTime (8);
        assignedTime = r.getDateTime (9);
        finishedTime = r.getDateTime (10);
        priority     = r.getInt (11);

        workerId     = safeParseUUID (r.getString (12));

        result       = r.getShort (13).to!JobResult;
        latestLogExcerpt = r.getString (14);

        data         = parseJsonString (r.getString (15));
    }
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

    this (ResultSet r) @trusted
    {
        import std.conv : to;
        assert (r.getMetaData.getColumnCount == 6);

        uuid        = UUID (r.getString (1));
        kind        = r.getShort (2).to!EventKind;
        moduleName  = r.getString (3);
        time        = r.getDateTime (4);

        title       = r.getString (5);
        text        = r.getString (6);
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
    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    // Jobs table
    stmt.executeUpdate (
        "CREATE TABLE IF NOT EXISTS jobs (
          uuid             UUID PRIMARY KEY,
          status           SMALLINT,
          module           TEXT NOT NULL,
          kind             TEXT NOT NULL,
          trigger          UUID,
          version          DEBVERSION,
          architecture     TEXT,
          time_created     TIMESTAMP NOT NULL,
          time_assigned    TIMESTAMP NOT NULL,
          time_finished    TIMESTAMP NOT NULL,
          priority         INTEGER,
          worker_id        UUID,
          result           SMALLINT,
          latest_log_excerpt TEXT,
          data             JSONB
        )"
    );

    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS jobs_status_kind_idx ON jobs (status, kind)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS jobs_trigger_idx ON jobs (trigger)");

    // Events table
    stmt.executeUpdate (
        "CREATE TABLE IF NOT EXISTS events (
          uuid             UUID PRIMARY KEY,
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
void updateJob (Connection conn, Job job) @trusted
{
    import vibe.data.json : serializeToJsonString;

    immutable sql = "INSERT INTO jobs
                    VALUES (?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?::timestamp,
                            ?::timestamp,
                            ?::timestamp,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?::jsonb
                        )
                    ON CONFLICT (uuid) DO UPDATE SET
                      status           = ?,
                      module           = ?,
                      kind             = ?,
                      trigger          = ?,
                      version          = ?,
                      architecture     = ?,
                      time_assigned    = ?::timestamp,
                      time_finished    = ?::timestamp,
                      priority         = ?,
                      worker_id        = ?,
                      result           = ?,
                      latest_log_excerpt = ?,
                      data             = ?::jsonb";

    auto ps = conn.prepareStatement (sql);
    scope (exit) ps.close ();

    ps.setString (1, job.uuid.toString);
    ps.setShort  (2, job.status.to!short);
    ps.setString (3, job.moduleName);
    ps.setString (4, job.kind);
    ps.setString (5, job.trigger.toString);
    ps.setString (6, job.ver);
    ps.setString (7, job.architecture);
    ps.setDateTime (8, job.createdTime);
    ps.setDateTime (9, job.assignedTime);
    ps.setDateTime (10, job.finishedTime);
    ps.setInt    (11, job.priority);
    ps.setString (12, job.workerId.toString);
    ps.setShort  (13, job.result.to!short);
    ps.setString (14, job.latestLogExcerpt);
    ps.setString (15, job.data.serializeToJsonString);

    ps.setShort  (16, job.status.to!short);
    ps.setString (17, job.moduleName);
    ps.setString (18, job.kind);
    ps.setString (19, job.trigger.toString);
    ps.setString (20, job.ver);
    ps.setString (21, job.architecture);
    ps.setDateTime (22, job.assignedTime);
    ps.setDateTime (23, job.finishedTime);
    ps.setInt    (24, job.priority);
    ps.setString (25, job.workerId.toString);
    ps.setShort  (26, job.result.to!short);
    ps.setString (27, job.latestLogExcerpt);
    ps.setString (28, job.data.serializeToJsonString);

    ps.executeUpdate ();
}

/**
 * Add a new job to the database.
 */
void addJob (Connection conn, Job job, LkModule mod, JobKind kind, UUID trigger)
{
    import laniakea.utils : currentDateTime;
    import std.array : empty;
    import std.string : format;

    job.uuid = randomUUID ();
    job.kind = kind;
    job.moduleName = mod;
    job.createdTime = currentDateTime;
    job.status = JobStatus.WAITING;
    job.trigger = trigger;

    logInfo ("Adding job '%s::%s/%s'", mod.to!string, kind.to!string, job.uuid.toString);
    conn.updateJob (job);
}

/**
 * Find jobs by their trigger ID.
 */
auto getJobsByTrigger (Connection conn, UUID triggerId, long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE trigger=? ORDER BY time_created DESC LIMIT ? OFFSET ?");
    scope (exit) ps.close ();

    ps.setString (1, triggerId.toString);
    ps.setLong   (3, offset);

    if (limit > 0)
        ps.setLong (2, limit);
    else
        ps.setLong (2, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!Job (ans);
}

/**
 * Return the amount of jobs caused by the given trigger
 */
auto countJobsByTrigger (Connection conn, UUID triggerId) @trusted
{
    auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM jobs WHERE trigger=?");
    scope (exit) ps.close ();
    ps.setString (1, triggerId.toString);

    Variant var;
    ps.executeUpdate (var);

    return var.get!long;
}

/**
 * Find jobs by their trigger ID and assigned version and architecture.
 */
auto getJobsByTriggerVerArch (Connection conn, UUID triggerId, const string ver, const string arch,
                              long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE trigger=?
                                        AND version=?
                                        AND architecture=?
                                      ORDER BY priority, time_created DESC
                                      LIMIT ? OFFSET ?");
    scope (exit) ps.close ();

    ps.setString (1, triggerId.toString);
    ps.setString (2, ver);
    ps.setString (3, arch);
    ps.setLong   (5, offset);

    if (limit > 0)
        ps.setLong  (4, limit);
    else
        ps.setLong  (4, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!Job (ans);
}

/**
 * Get jobs that are not complete yet.
 */
auto getPendingJobs (Connection conn, long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE status != ?
                                      ORDER BY priority, time_created DESC
                                      LIMIT ? OFFSET ?");
    scope (exit) ps.close ();

    ps.setShort (1, JobStatus.DONE);
    ps.setLong  (3, offset);

    if (limit > 0)
        ps.setLong  (2, limit);
    else
        ps.setLong  (2, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!Job (ans);
}

/**
 * Get jobs that are not complete yet for a specific module @mod
 */
auto getPendingJobs (Connection conn, LkModule mod, long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE status != ? AND module = ?
                                      ORDER BY priority, time_created DESC
                                      LIMIT ? OFFSET ?");
    scope (exit) ps.close ();

    ps.setShort (1, JobStatus.DONE);
    ps.setString (2, mod);
    ps.setLong  (4, offset);

    if (limit > 0)
        ps.setLong  (3, limit);
    else
        ps.setLong  (3, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!Job (ans);
}

/**
 * Return the amount of jobs in the queue.
 */
auto countPendingJobs (Connection conn) @trusted
{
    auto ps = conn.prepareStatement ("SELECT COUNT(*) FROM jobs WHERE status != ?");
    scope (exit) ps.close ();
    ps.setShort (1, JobStatus.DONE);

    Variant var;
    ps.executeUpdate (var);

    return var.get!long;
}

/**
 * Find a job by its unique ID.
 */
auto getJobById (Connection conn, string uuid) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE uuid=?");
    scope (exit) ps.close ();

    ps.setString (1, uuid);
    auto ans = ps.executeQuery ();

    return rowsToOne!Job (ans);
}

/**
 * Fetch the name of the worker assigned to this job
 */
auto getJobWorkerName (Connection conn, Job job) @trusted
{
    auto ps = conn.prepareStatement ("SELECT machine_name FROM workers WHERE uuid=?");
    scope (exit) ps.close ();

    ps.setString (1, job.workerId.toString);
    auto ans = ps.executeQuery ();

    string wname;
    if (ans.getFetchSize > 0) {
        ans.first ();
        wname = ans.getString (1);
    }

    return wname;
}

/**
 * Change result of job.
 */
auto setJobResult (Connection conn, UUID jobId, JobResult result) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET result=? WHERE uuid=? RETURNING *");
    scope (exit) ps.close ();

    ps.setShort  (1, result.to!short);
    ps.setString (2, jobId.toString);

    auto ans = ps.executeQuery ();
    return rowsToOne!Job (ans);
}

/**
 * Change status of job.
 */
bool setJobStatus (Connection conn, UUID jobId, JobStatus status) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET status=? WHERE uuid=?");
    scope (exit) ps.close ();

    ps.setShort  (1, status.to!short);
    ps.setString (2, jobId.toString);

    ps.executeUpdate ();
    return true;
}

/**
 * Set the latest log excerpt
 */
bool setJobLogExcerpt (Connection conn, UUID jobId, string excerpt) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET latest_log_excerpt=? WHERE uuid=?");
    scope (exit) ps.close ();

    ps.setString (1, excerpt);
    ps.setString (2, jobId.toString);

    ps.executeUpdate ();
    return true;
}


/**
 * Remove a job from the database entirely.
 */
void deleteJob (Connection conn, UUID jobId) @trusted
{
    auto ps = conn.prepareStatement ("DELETE FROM jobs WHERE uuid=?");
    scope (exit) ps.close ();

    ps.setString (1, jobId.toString);
    ps.executeUpdate ();
}

/**
 * Add a new event to the database (using a DB connection)
 */
void addEvent (Connection conn, EventKind kind, string title, string text) @trusted
{
    import laniakea.localconfig : LocalConfig;
    const conf = LocalConfig.get;


    auto ps = conn.prepareStatement ("INSERT INTO events
                                      VALUES (?,
                                              ?,
                                              ?,
                                              now(),
                                              ?,
                                              ?
                                             )");
    scope (exit) ps.close ();

    ps.setString (1, randomUUID ().toString);
    ps.setShort  (2, kind.to!short);
    ps.setString (3, conf.currentModule);
    ps.setString (4, title);
    ps.setString (5, text);

    ps.executeUpdate ();
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
