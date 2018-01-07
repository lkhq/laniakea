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
struct Job
{
    import vibe.data.serialization : name;

    UUID uuid;

    JobStatus status; /// Status of this job

    @name("module")
    string moduleName; /// the name of the module responsible for this job
    string kind;       /// kind of the job

    string title;     /// A human-readable title of this job

    UUID trigger;     /// ID of the entity responsible for triggering this job's creation
    string architecture = "any"; /// Architecture this job can run on, "any" in case the architecture does not matter

    DateTime createdTime;  /// Time when this job was created.
    DateTime assignedTime; /// Time when this job was assigned to a worker.
    DateTime finishedTime; /// Time when this job was finished.

    string worker;        /// The person/system/tool this job is assigned to
    UUID   workerId;      /// Unique ID of the entity the job is assigned to

    string latestLogExcerpt;   /// An excerpt of the current job log

    JobResult result;

    Json data;

    this (ResultSet r) @trusted
    {
        import std.conv : to;
        import vibe.data.json : parseJsonString;
        assert (r.getMetaData.getColumnCount == 15);

        uuid         = UUID (r.getString (1));
        status       = r.getShort (2).to!JobStatus;
        moduleName   = r.getString (3);
        kind         = r.getString (4);
        title        = r.getString (5);
        trigger      = UUID (r.getString (6));
        architecture = r.getString (7);

        createdTime  = r.getDateTime (8);
        assignedTime = r.getDateTime (9);
        finishedTime = r.getDateTime (10);

        worker       = r.getString (11);
        workerId     = UUID (r.getString (12));

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
          title            TEXT,
          trigger          VARCHAR(32),
          architecture     TEXT,
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
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            to_timestamp($8),
                            to_timestamp($9),
                            to_timestamp($10),
                            $11,
                            $12,
                            $13,
                            $14,
                            $15::jsonb
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      status           = $2,
                      module           = $3,
                      kind             = $4,
                      title            = $5,
                      trigger          = $6,
                      architecture     = $7,
                      time_assigned    = to_timestamp($9),
                      time_finished    = to_timestamp($10),
                      worker_name      = $11,
                      worker_id        = $12,
                      result           = $13,
                      latest_log_excerpt = $14,
                      data             = $15::jsonb";

    auto ps = conn.prepareStatement (sql);
    scope (exit) ps.close ();

    ps.setString (1, job.uuid.toString);
    ps.setShort  (2, job.status.to!short);
    ps.setString (1, job.moduleName);
    ps.setString (1, job.kind);
    ps.setString (1, job.title);
    ps.setString (1, job.trigger.toString);
    ps.setString (1, job.architecture);
    ps.setDateTime (1, job.createdTime);
    ps.setDateTime (1, job.assignedTime);
    ps.setDateTime (1, job.finishedTime);
    ps.setString (1, job.worker);
    ps.setString (1, job.workerId.toString);
    ps.setShort  (2, job.result.to!short);
    ps.setString (1, job.latestLogExcerpt);
    ps.setString (1, job.data.serializeToJsonString);

    ps.executeUpdate ();
}

/**
 * Add a new job to the database.
 */
void addJob (Connection conn, Job job, UUID trigger)
{
    import laniakea.utils : currentDateTime;
    import std.array : empty;
    import std.string : format;

    job.uuid = randomUUID ();
    job.createdTime = currentDateTime;
    job.status = JobStatus.WAITING;
    job.trigger = trigger;

    // set a dummy titke for displaying information in UIs which do not
    // have knowledge of all Laniakea modules
    if (job.title.empty) {
        job.title = "%s %s job".format (job.moduleName, job.kind);
    }

    logInfo ("Adding job '%s'", job.uuid.toString);
    conn.updateJob (job);
}

/**
 * Find jobs by their trigger ID.
 */
auto getJobsByTrigger (Connection conn, UUID triggerId, long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM jobs WHERE trigger=$1 ORDER BY time_created DESC LIMIT $2 OFFSET $3");
    scope (exit) ps.close ();

    ps.setString (1, triggerId.toString);
    ps.setLong  (3, offset);

    if (limit > 0)
        ps.setLong  (3, limit);
    else
        ps.setLong  (3, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!Job (ans);
}

/**
 * Change result of job.
 */
auto setJobResult (Connection conn, UUID jobId, JobResult result) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET result=$1 WHERE uuid=$2 RETURNING *");
    scope (exit) ps.close ();

    ps.setShort (1, result.to!short);
    ps.setString (2, jobId.toString);

    auto ans = ps.executeQuery ();
    return rowsToOne!Job (ans);
}

/**
 * Change status of job.
 */
bool setJobStatus (Connection conn, UUID jobId, JobStatus status) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET status=$1 WHERE uuid=$2");
    scope (exit) ps.close ();

    ps.setShort (1, status.to!short);
    ps.setString (2, jobId.toString);

    ps.executeUpdate ();
    return true;
}

/**
 * Set the latest log excerpt
 */
bool setJobLogExcerpt (Connection conn, UUID jobId, string excerpt) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE jobs SET latest_log_excerpt=$1 WHERE uuid=$2");
    scope (exit) ps.close ();

    ps.setString (1, excerpt);
    ps.setString (2, jobId.toString);

    ps.executeUpdate ();
    return true;
}

// FIXME
version (none) {
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

}
