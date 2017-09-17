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

module app;

import std.exception : enforce;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.web.web;
import vibe.http.fileserver;
import diet.html;

import laniakea.localconfig;

import web.webconfig;

import web.spearsweb;
import web.syncweb;
import web.depcheckweb;
import web.workersweb;
import web.jobsweb;
import web.isoimagesweb;

class LaniakeaWebService {
    GlobalInfo ginfo;

	private {
        WebConfig wconf;
	}

    this (WebConfig conf)
    {
        wconf = conf;
        ginfo = wconf.ginfo;
    }

	// overrides the path that gets inferred from the method name to
	// "GET /"
	@path("/")
    void getOverview()
	{
		render!("overview.dt", ginfo);
	}
}

private string findPublicDir ()
{
    import std.file : exists, thisExePath;
    import std.path : buildPath, buildNormalizedPath;

    immutable exePath = thisExePath;
    string staticDir = buildPath (exePath, "public");
    if (staticDir.exists)
        return staticDir;
    staticDir = buildNormalizedPath (exePath, "..", "..", "..", "..", "src", "web", "public");
    if (staticDir.exists)
        return staticDir;
    return "public/";
}

shared static this ()
{
    import core.memory;

	// Create the router that will dispatch each request to the proper handler method
	auto router = new URLRouter;

    // Initialize the global and app-specific configuration
    LocalConfig.get.load (LkModule.WEB);
    auto wconf = new WebConfig (LocalConfig.get);
    wconf.load ();

	// Register individual service classes to the router
	router.registerWebInterface (new LaniakeaWebService (wconf));
    router.registerWebInterface (new SpearsWebService (wconf));
    router.registerWebInterface (new SynchrotronWebService (wconf));
    router.registerWebInterface (new DepcheckWebService (wconf));
    router.registerWebInterface (new WorkersWebService (wconf));
    router.registerWebInterface (new IsoImagesWebService (wconf));
    router.registerWebInterface (new JobsWebService (wconf));

	// All requests that haven't been handled by the web interface registered above
	// will be handled by looking for a matching file in the public/ folder.
    immutable publicDir = findPublicDir ();
    logInfo ("Static data from: %s", publicDir);
	router.get("*", serveStaticFiles (publicDir));

	// Start up the HTTP server
	auto settings = new HTTPServerSettings;
	settings.port = wconf.port;
	settings.bindAddresses = ["::1", "127.0.0.1"];
	settings.sessionStore = new MemorySessionStore;
	listenHTTP (settings, router);

	logInfo("Listening on 127.0.0.1:%s");

    // clean up stuff left from the initialization explicitly
    GC.collect ();
}

int main()
{
	import vibe.core.core : runApplication;

	version (unittest) {
		return 0;
	} else {
		return runApplication();
	}
}
