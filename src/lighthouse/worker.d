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
import std.typecons : Nullable;
import vibe.data.json;

import c.zmq;
import laniakea.logging;
import laniakea.db;
import laniakea.utils : currentDateTime;
import laniakea.db.schema.workers : SparkWorker;

import lighthouse.utils;

class LighthouseWorker {
    private {
        zsock_t *socket;

        Database db;
        Connection conn;
        SessionFactory sFactory;
    }

    this (zsock_t *sock, SessionFactory factory)
    {
        socket = sock;

        db = Database.get;
        conn = db.getConnection ();

        sFactory = factory;
    }

    ~this ()
    {
        db.dropConnection (conn);
    }

    /**
     * Read job request and return a job matching the request or
     * JSON-null in case we couldn't find any job.
     */
    private string processJobRequest (Json jreq)
    {
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;
        auto architectures = jreq["architectures"].get!(Json[]);

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        // update information about this client
        auto worker = session.createQuery ("FROM SparkWorker WHERE uuid_s=:id")
                             .setParameter ("id", clientId)
                             .uniqueResult!SparkWorker;
        // we might have a new machine, so set the ID again to create an empty new worker
        if (worker is null) {
            import std.uuid : parseUUID;
            // this may throw an exception which is caought and sent back to the worker
            // (the worker then has the oportunity to fix its UUID)
            const clientUUID = parseUUID (clientId);

            worker = new SparkWorker;
            worker.uuid = clientUUID;
            worker.machineName = clientName;
            worker.createdTime = currentDateTime;
            worker.enabled = true;
            session.save (worker);
        }
        worker.lastPing = currentDateTime;
        worker.accepts = jreq["accepts"].deserializeJson!(string[]);
        session.update (worker);

        string jobData = null.serializeToJsonString;
        foreach (ref archJ; architectures) {
            immutable arch = archJ.get!string;


            auto ps = conn.prepareStatement ("UPDATE jobs SET
                                              status=?,
                                              worker_name=?,
                                              worker_id=?,
                                              time_assigned=now()
                                            WHERE
                                              status=? AND (architecture=? OR architecture='any')
                                            RETURNING *");
            scope (exit) ps.close ();

            ps.setShort  (1, JobStatus.SCHEDULED.to!short);
            ps.setString (2, clientName);
            ps.setString (3, clientId);
            ps.setShort  (4, JobStatus.WAITING.to!short);
            ps.setString (5, arch);

            auto ans = ps.executeQuery ();

            // use the first job with a matching architecture
            const job = ans.rowsToOne!Job;
            if (!job.isNull) {
                jobData = job.serializeToJsonString ();
                break;
            }
        }

        return jobData;
    }

    /**
     * If the worker actually accepts a job we sent to it and starts
     * working on it, this method is triggered.
     * On success, we wend the job back again.
     */
    private string processJobAcceptedRequest (Json jreq)
    {
        auto jobId = UUID (jreq["uuid"].get!string);
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;

        conn.setJobStatus (jobId, JobStatus.RUNNING);
        return Json(null).serializeToJsonString;
    }

    /**
     * If the worker rejects a job that we gave to it (for example because
     * it ran out of resources and can't process it), we reset the
     * status of the respectice job in the database.
     */
    private string processJobRejectedRequest (Json jreq)
    {
        auto jobId = jreq["lkid"].get!string;
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;


        auto ps1 = conn.prepareStatement ("UPDATE jobs SET
                                           status=?
                                           worker_name=?,
                                           worker_id=?
                                         WHERE
                                           uuid=? AND status=?
                                         RETURNING *");
        scope (exit) ps1.close ();

        ps1.setShort  (1, JobStatus.WAITING.to!short);
        ps1.setString (2, "");
        ps1.setString (3, UUID ().toString);
        ps1.setString (4, jobId);
        ps1.setShort  (5, JobStatus.SCHEDULED.to!short);

        auto res = ps1.executeQuery ();

        if (res.getFetchSize () == 0) {
            // we also want to allow workers to reject a job that they have already accepted - if the workers
            // change their mind that late, it's usually a sign that something broke. In this case, we don't want
            // to block a possibly important job though, and rather have another worker take it instead.
            // NOTE: Should we log this behavior?
            auto ps2 = conn.prepareStatement ("UPDATE jobs SET
                                                 status=?
                                                 worker_name=?,
                                                 worker_id=?
                                               WHERE
                                                 uuid=? AND status=?
                                               RETURNING *");
            scope (exit) ps2.close ();

            ps2.setShort  (1, JobStatus.WAITING.to!short);
            ps2.setString (2, "");
            ps2.setString (3, UUID ().toString);
            ps2.setString (4, jobId);
            ps2.setShort  (5, JobStatus.RUNNING.to!short);

            ps2.executeQuery ();
        }

        return Json(null).serializeToJsonString;
    }

    /**
     * Run if the job has finished and we are expecting results from the worker
     * to be uploaded.
     */
    private string processJobFinishedRequest (Json jreq, bool success)
    {
        auto jobId = jreq["lkid"].get!string;
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;

        // we use the maybe values here, as we can only be really sure as soon as
        // the worker has uploaded the job artifacts and the responsible Laniakea
        // module has verified them.
        auto jobResult = JobResult.MAYBE_SUCCESS;
        if (!success)
            jobResult = JobResult.MAYBE_FAILURE;


        auto ps = conn.prepareStatement ("UPDATE jobs SET
                                             status=?,
                                             result=?,
                                             time_finished=now()
                                           WHERE
                                             uuid=? AND status=?");
        scope (exit) ps.close ();

        ps.setShort  (1, JobStatus.DONE.to!short);
        ps.setShort  (2, jobResult.to!short);
        ps.setString (3, jobId);
        ps.setShort  (4, JobStatus.RUNNING.to!short);

        ps.executeQuery ();

        return Json(null).serializeToJsonString;
    }

    /**
     * When a job is running, the worker will periodically send
     * status information, which we collect here.
     */
    private void processJobStatusRequest (Json jreq)
    {
        auto jobId = UUID (jreq["uuid"].get!string);
        auto clientName = jreq["machine_name"].get!string;
        auto clientId = jreq["machine_id"].get!string;
        auto logExcerpt = jreq["log_excerpt"].get!string;

        // update last seen data

        conn.updateWorkerPing (clientId);

        // update log & status data
        conn.setJobLogExcerpt (jobId, logExcerpt);
    }

    private Nullable!string processJsonRequest (string json)
    {
        Json j;
        try {
            j = parseJsonString (json);
        } catch (Exception e) {
            logInfo ("Invalid request received: %s", e.to!string);
            return Nullable!string (["error": e.to!string].serializeToJsonString);
        }

        if ("request" !in j) {
            return Nullable!string (["error": "Request was malformed."].serializeToJsonString);
        }

        auto req = j["request"].to!string;

        Nullable!string res;
        try {
            switch (req) {
                case "job":
                    res = processJobRequest (j);
                    break;
                case "job-accepted":
                    res = processJobAcceptedRequest (j);
                    break;
                case "job-rejected":
                    res = processJobRejectedRequest (j);
                    break;
                case "job-status":
                    processJobStatusRequest (j);
                    res.nullify ();
                    break;
                case "job-success":
                    res = processJobFinishedRequest (j, true);
                    break;
                case "job-failed":
                    res = processJobFinishedRequest (j, false);
                    break;
                default:
                    return Nullable!string (["error": "Request type is unknown."].serializeToJsonString);
            }
        } catch (Exception e) {
            logError ("Failed to handle request: %s :: %s", e.to!string, json);
            return Nullable!string (["error": "Failed to handle request."].serializeToJsonString);
        }

        return res;
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
        if (rmsg.isNull)
            return;

        auto reply = frameForStr (rmsg.get);
        scope (exit) zframe_destroy (&reply);

        // send reply back
        zframe_send (&identity, socket, ZFRAME_REUSE + ZFRAME_MORE);
        zframe_send (&reply, socket, ZFRAME_REUSE);
    }
}
