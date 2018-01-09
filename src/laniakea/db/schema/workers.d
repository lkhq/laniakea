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

module laniakea.db.schema.workers;
@safe:

import std.datetime : DateTime;
import laniakea.db.utils;

/**
 * State this worker is in.
 **/
enum WorkerStatus
{
    UNKNOWN,
    ACTIVE,
    IDLE,
    MISSING,
    DEAD
}

/**
 * An external machine/service that takes tasks from a Lighthouse server.
 **/
@Table ("workers")
class SparkWorker {
    mixin UUIDProperty;

    string machineName;   /// The machine/worker name
    string owner;         /// Owner of this worker
    DateTime createdTime; /// Time when this worker was created

    string[] accepts;    /// Modules this worker will accept jobs for
    mixin (JsonDatabaseField!("accepts", "accepts", "string[]"));

    WorkerStatus status; /// Status/health of this machine
    mixin (EnumDatabaseField!("status", "status", "WorkerStatus"));

    bool enabled;        /// Whether this worker should receive jobs or not

    DateTime lastPing;   /// Time when we last got a message from the worker

    UUID lastJob;        /// The last job that was assigned to this worker
    @property @Column ("last_job") string lastJob_s () { return lastJob.toString; }
    @property void lastJob_s (string s) { lastJob = UUID (s); }
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    auto factory = db.newSessionFactory! (SparkWorker);
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData().updateDBSchema (conn, false, true);

    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    // ensure we use the right datatypes - the ORM is not smart enough to
    // figure out the proper types
    stmt.executeUpdate (
        "ALTER TABLE workers
         ALTER COLUMN uuid TYPE UUID USING uuid::uuid,
         ALTER COLUMN last_job TYPE UUID USING uuid::uuid,
         ALTER COLUMN accepts TYPE JSONB USING accepts::jsonb;"
    );
}

void updateWorkerPing (Connection conn, string workerId) @trusted
{
    auto ps = conn.prepareStatement ("UPDATE workers SET last_ping=now() WHERE uuid=$1");
    scope (exit) ps.close ();

    ps.setString (1, workerId);
    ps.executeQuery ();
}

void updateWorkerPing (Connection conn, UUID workerId) @trusted
{
    updateWorkerPing (conn, workerId.toString);
}
