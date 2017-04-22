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

import c.zmq;
import c.zmq.zproxy;
import core.thread : Thread;
import std.string : toStringz, fromStringz;
import std.parallelism : totalCPUs;

import lighthouse.utils;
import laniakea.logging;
import lighthouse.worker;

/**
 * Listen for signals and call for the worker
 * to handle requests.
 */
void
serverWorkerThread (int threadId)
{
    auto workerSock = zsock_new (ZMQ_DEALER);
    scope (exit) zsock_destroy (&workerSock);

    auto r = zsock_connect (workerSock, "inproc://backend".toStringz);
    assert (r == 0);
    logDebug ("Started new worker thread.");

    auto worker = new LighthouseWorker (workerSock);
    while (true) {
        // receive reply envelope and message
        auto msg = zmsg_recv (workerSock);
        if (msg is null) {
            logWarning ("Received NULL message.");
            continue;
        }
        scope (exit) zmsg_destroy (&msg);

        // have the worker handle the request
        worker.handleRequest (msg);
    }
}

/**
 * Spawn server proxy and worker threads.
 */
void runServer ()
{
        //  Connect backend to frontend via a proxy
        auto proxy = zactor_new (&zproxy, null);
        assert (proxy);

        zstr_sendx (proxy, "FRONTEND".toStringz, "ROUTER".toStringz, "tcp://*:5570".toStringz, null);
        zsock_wait (proxy);
        zstr_sendx (proxy, "BACKEND".toStringz, "DEALER".toStringz, "inproc://backend".toStringz, null);
        zsock_wait (proxy);

        // determine the number of worker threads we want to spawn
        auto maxThreads = totalCPUs - 1;
        if (maxThreads <= 0)
            maxThreads = 1;
        for (auto i = 0; i < maxThreads; i++)
            new Thread ({ serverWorkerThread (i); }).start ();
}
