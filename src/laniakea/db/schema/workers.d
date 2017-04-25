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

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;

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
    @name("_id") BsonObjectID id;

    string machineName; /// The machine/worker name
    string machineId;   /// The machine-id as defined in /etc/machine-id for this system

    WorkerStatus status; /// Status/health of this machine

    string owner; /// Owner of this worker

    BsonDate lastPing;

    BsonObjectID lastJob; /// The last job that was assigned to this worker
}
