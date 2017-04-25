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

import c.zmq;
import laniakea.logging;

import lighthouse.utils;

class LighthouseWorker {
    private {
        zsock_t *socket;
    }

    this (zsock_t *sock)
    {
        socket = sock;
    }

    private string processJobRequest (Json jreq)
    {
        auto client_name = jreq["machine_name"].get!string;
        auto client_id = jreq["machine_id"].get!string;

        auto accepted_jobs = jreq["accepts"].get!(Json[]);

        return ["error": "Not implemented yet."].serializeToJsonString;
    }

    private string processJobAcceptedRequest (Json jreq)
    {
        return ["status": "OK"].serializeToJsonString;
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
                default:
                    return ["error": "Request type is unknown."].serializeToJsonString;
            }
        } catch (Exception e) {
            logInfo ("Invalid request received: %s", e.to!string);
            return ["error": "Request was malformed."].serializeToJsonString;
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
