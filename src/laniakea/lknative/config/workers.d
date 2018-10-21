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

import std.uuid : UUID;
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
class SparkWorker {
    UUID uuid;

    string machineName;   /// The machine/worker name
    string owner;   /// Owner of this worker
    DateTime createdTime; /// Time when this worker was created

    string[] accepts;    /// Modules this worker will accept jobs for

    WorkerStatus status; /// Status/health of this machine

    bool enabled;        /// Whether this worker should receive jobs or not

    DateTime lastPing;   /// Time when we last got a message from the worker

    UUID lastJob;        /// The last job that was assigned to this worker
}
