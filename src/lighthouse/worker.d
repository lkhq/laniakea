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

        logInfo ("HANDLE: %s", json);

        auto rmsg = "{ \"NOOP\": true }";
        auto reply = frameForStr (rmsg);
        scope (exit) zframe_destroy (&reply);

        // send reply back
        zframe_send (&identity, socket, ZFRAME_REUSE + ZFRAME_MORE);
        zframe_send (&reply, socket, ZFRAME_REUSE);
    }
}
