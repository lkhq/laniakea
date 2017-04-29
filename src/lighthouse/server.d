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
import std.string : toStringz, fromStringz, format;
import std.parallelism : totalCPUs;

import laniakea.logging;
import laniakea.localconfig;
import lighthouse.utils;
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
            logDebug ("Received NULL message.");
            continue;
        }
        scope (exit) zmsg_destroy (&msg);

        // have the worker handle the request
        worker.handleRequest (msg);
    }
}

/**
 * Create and set up ZeroMQ authentication engine
 * using the certificates registered with Laniakea.
 */
zactor_t *createAuthEngine (bool verbose)
{
    import c.zmq.zauth : zauth;

    auto conf = LocalConfig.get;

    //  create and start authentication engine
    auto auth = zactor_new (&zauth, null);
    assert (auth !is null);

    if (verbose) {
        zstr_send (auth, "VERBOSE".toStringz);
        zsock_wait (auth);
    }

    // allow connections from all IPs
    zstr_sendx (auth, "ALLOW".toStringz, "*".toStringz, null);
    zsock_wait (auth);

    // tell the authenticator to use the certificate store in trustedCurveCertsDir
    zstr_sendx (auth, "CURVE".toStringz,
                conf.trustedCurveCertsDir.toStringz,
                null);
    zsock_wait (auth);

    return auth;
}

/**
 * Load the certificate registered for this
 * machine/service.
 */
zcert_t *loadServiceCertificate ()
{
    auto conf = LocalConfig.get;

    // load the service private certificate
    auto cert = zcert_load (conf.serviceCurveCertFname.toStringz);
    if (cert is null)
        throw new Exception ("Unable to load service certificate: %s".format (getErrnoStr()));

    return cert;
}

/**
 * Spawn server proxy and worker threads.
 */
void runServer (bool verbose)
{
    import c.zmq.zsys;
    import c.zmq.zmonitor;

    // make CTRL+C work - maybe we want our own interrupt handler in future?
    zsys_handler_set (null);

    // load certificates and authentication engine
    auto serviceCert = loadServiceCertificate ();
    scope (exit) zcert_destroy (&serviceCert);

    auto authEngine = createAuthEngine (verbose);
    scope (exit) zactor_destroy (&authEngine); // NOTE: Should we really destroy this at the end of scope? - it seems to ha effects

    // new proxy connection to communicate with the outside world
    auto proxy = zactor_new (&zproxy, null);
    assert (proxy);

    // apply the server certificate to our proxy socket on the frontend side
    // (internally we of course don't need to encrypt anything)
    zsock_set_curve_server (proxy, 1);
    zstr_sendx (proxy,
                "CURVE".toStringz,
                "FRONTEND".toStringz,
                zcert_public_txt (serviceCert),
                zcert_secret_txt (serviceCert),
                null);
    zsock_wait (proxy);

    //  connect backend to frontend via a proxy
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
