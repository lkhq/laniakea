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

module lighthouse.worker;

import std.conv : to;
import std.string : toStringz, fromStringz;
import vibe.data.json;
import vibe.db.mongo.mongo;

import c.zmq;
import laniakea.logging;
import laniakea.db;

import lighthouse.utils;

class LighthouseWorker {
    private {
        zsock_t *socket;
        MongoCollection collWorkers;
        MongoCollection collJobs;
    }

    this (zsock_t *sock)
    {
        socket = sock;

        auto db = Database.get;
        collWorkers = db.collWorkers ();
        collJobs = db.collJobs ();
    }

    /**
     * Read job request and return a job matching the request or
     * JSON-null in case we couldn't find any job.
     */
    private string processJobRequest (Json jreq)
    {
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;

        auto acceptedJobs = jreq["accepts"].get!(Json[]);
        auto architectures = jreq["architectures"].get!(Json[]);

        // update information about this client
        collWorkers.findAndModifyExt (["machineId": clientId],
                                      ["$set": [
                                            "machineId": Bson(clientId),
                                            "machineName": Bson(clientName),
                                            "lastPing": Bson(currentTimeAsBsonDate)
                                            ]],
                                      ["new": true, "upsert": true]);

        Bson job;
        foreach (ref arch; architectures) {
            job = collJobs.findAndModifyExt (["status": Bson(JobStatus.WAITING.to!int),
                                              "architecture": Bson(arch)],
                                            ["$set": [
                                                "status": Bson(JobStatus.SCHEDULED.to!int),
                                                "worker": Bson(clientName),
                                                "workerId": Bson(clientId),
                                                "assignedTime": Bson(currentTimeAsBsonDate)
                                                ]],
                                            ["new": true]);
            // use the first job with a matching architecture
            if (job.type != Json.Type.null_)
                break;
        }

        return job.serializeToJsonString;
    }

    /**
     * If the worker actually accepts a job we sent to it and starts
     * working on it, this method is triggered.
     * On success, we wend the job back again.
     */
    private string processJobAcceptedRequest (Json jreq)
    {
        auto jobId = jreq["_id"].get!string;
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;

        auto job = collJobs.findAndModifyExt (["status": Bson(JobStatus.SCHEDULED.to!int),
                                               "_id": Bson(jobId)],
                                        ["$set": [
                                            "status": Bson(JobStatus.RUNNING.to!int)
                                            ]],
                                        ["new": true]);

        return job.serializeToJsonString;
    }

    /**
     * If the worker rejects a job that we gave to it (for example because
     * it ran out of resources and can't process it), we reset the
     * status of the respectice job in the database.
     */
    private string processJobDeniedRequest (Json jreq)
    {
        auto jobId = jreq["_id"].get!string;
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;

        collJobs.findAndModify (["status": Bson(JobStatus.SCHEDULED.to!int),
                                "_id": Bson(jobId)],
                                ["$set": [
                                    "status": Bson(JobStatus.WAITING.to!int)
                                ]]);

        return Json(null).serializeToJsonString;
    }

    /**
     * When a job is running, the worker will periodically send
     * status information, which we collect here.
     */
    private string processJobStatusRequest (Json jreq)
    {
        auto jobId = jreq["_id"].get!string;
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;
        auto logExcerpt = jreq["log_excerpt"].get!string;

        // update last seen data
        collWorkers.findAndModify (["machineId": clientId],
                                   ["$set": ["lastPing": Bson(currentTimeAsBsonDate)]]);

        // update log & status data
        collJobs.findAndModify (["_id": Bson(jobId)],
                                ["$set": ["latestLogExcerpt": Bson(logExcerpt)]]);
        return Json(null).serializeToJsonString;
    }

    private string processJsonRequest (string json)
    {
        Json j;
        try {
            j = parseJsonString (json);
        } catch (Exception e) {
            logInfo ("Invalid request received: %s", e.to!string);
            return ["error": e.to!string].serializeToJsonString;
        }

        if ("request" !in j) {
            return ["error": "Request was malformed."].serializeToJsonString;
        }

        auto req = j["request"].to!string;

        try {
            switch (req) {
                case "job":
                    return processJobRequest (j);
                case "job-accepted":
                    return processJobAcceptedRequest (j);
                case "job-denied":
                    return processJobDeniedRequest (j);
                case "job-status":
                    return processJobStatusRequest (j);
                default:
                    return ["error": "Request type is unknown."].serializeToJsonString;
            }
        } catch (Exception e) {
            logInfo ("Failed to handle request: %s", e.to!string);
            return ["error": "Failed to handle request."].serializeToJsonString;
        }
    }

    public void handleRequest (zmsg_t *msg)
    {
        import core.stdc.stdlib : free;

        zframe_t *identity = zmsg_pop (msg);
        scope (exit) zframe_destroy (&identity);

        zframe_t *content = zmsg_pop (msg);
        assert (content);
        scope (exit) zframe_destroy (&content);

        auto frData = zframe_strdup (content);
        auto json = to!string(frData.fromStringz);
        free (frData);

        // process JSON query and send reply
        auto rmsg = processJsonRequest (json);

        auto reply = frameForStr (rmsg);
        scope (exit) zframe_destroy (&reply);

        // send reply back
        zframe_send (&identity, socket, ZFRAME_REUSE + ZFRAME_MORE);
        zframe_send (&reply, socket, ZFRAME_REUSE);
    }
}
