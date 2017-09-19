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
struct SparkWorker {
    LkId lkid;

    string machineName;   /// The machine/worker name
    string machineId;     /// The machine-id as defined in /etc/machine-id for this system
    string owner;         /// Owner of this worker
    DateTime createdTime; /// Time when this worker was created

    string[] accepts;    /// Modules this worker will accept jobs for
    WorkerStatus status; /// Status/health of this machine
    bool enabled;        /// Whether this worker should receive jobs or not

    DateTime lastPing;   /// Time when we last got a message from the worker
    LkId lastJob = "";   /// The last job that was assigned to this worker

    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &machineName,
                 &machineId,
                 &owner,
                 &createdTime,
                 &accepts,
                 &status,
                 &enabled,
                 &lastPing,
                 &lastJob
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

    conn.exec (
        "CREATE TABLE IF NOT EXISTS workers (
          lkid VARCHAR(32) PRIMARY KEY,
          name             TEXT NOT NULL,
          identifier       TEXT NOT NULL UNIQUE,
          owner            TEXT,
          time_created     TIMESTAMP,
          accepts          JSONB,
          status           SMALLINT,
          enabled          BOOLEAN,
          last_ping        TIMESTAMP,
          last_job         VARCHAR(32)
        )"
    );
}

/**
 * Add/update a worker.
 */
void update (PgConnection conn, SparkWorker worker) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO workers
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            to_timestamp($5),
                            $6::jsonb,
                            $7,
                            $8,
                            to_timestamp($9),
                            $10
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      name = $2,
                      identifier = $3,
                      owner      = $4,
                      accepts    = $6::jsonb,
                      status     = $7,
                      enabled    = $8,
                      last_ping  = to_timestamp($9),
                      last_job   = $10";

    p.setParams (worker.lkid,
                 worker.machineName,
                 worker.machineId,
                 worker.owner,
                 worker.createdTime,
                 worker.accepts,
                 worker.status,
                 worker.enabled,
                 worker.lastPing,
                 worker.lastJob
    );

    conn.execParams (p);
}

auto getWorkerByMachineId (PgConnection conn, string machineId) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM workers WHERE identifier=$1";
    p.setParams (machineId);

    auto ans = conn.execParams(p);
    return rowsToOne!SparkWorker (ans);
}

void updateWorkerPing (PgConnection conn, string workerId) @trusted
{
    conn.exec ("UPDATE workers SET last_ping=now() WHERE identifier=workerId");
}

auto getWorkers (PgConnection conn) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM workers ORDER BY name";
    auto ans = conn.execParams(p);
    return rowsTo!SparkWorker (ans);
}
