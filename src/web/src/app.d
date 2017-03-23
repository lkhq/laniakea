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
import vibe.http.fileserver;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;

import laniakea.db;
import laniakea.localconfig;

class LaniakeaService {
    string serviceName = "Laniakea";

	private {
        Database db;
	}

    this ()
    {
        db = Database.get;
    }

	// overrides the path that gets inferred from the method name to
	// "GET /"
	@path("/")
    void getOverview()
	{
		render!("overview.dt", serviceName);
	}

    @path("/migration/excuses")
	void getMigrationExcuses ()
	{
        auto collExcuses = db.getCollection ("spears.excuses");
        auto excuses = collExcuses.find!SpearsExcuse;
		render!("migration/excuses.dt", serviceName, excuses);
	}

    @path("/migration/excuses/:source/:version")
    void getMigrationExcuseDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        immutable sourcePackage = req.params["source"];
        immutable newVersion = req.params["version"];

        auto collExcuses = db.getCollection ("spears.excuses");
        auto excuse = collExcuses.findOne!SpearsExcuse (["sourcePackage": sourcePackage, "newVersion": newVersion]);
        if (excuse.isNull) {
            res.statusCode = 404;
            res.writeBody("");
            return;
        }

        render!("migration/excuse-details.dt", serviceName, excuse);
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
    logInfo (staticDir);
    if (staticDir.exists)
        return staticDir;
    return "public/";
}

shared static this ()
{
	// Create the router that will dispatch each request to the proper handler method
	auto router = new URLRouter;

    LocalConfig.get.load (LkModule.WEB);

	// Register our service class as a web interface. Each public method
	// will be mapped to a route in the URLRouter
	router.registerWebInterface (new LaniakeaService);

	// All requests that haven't been handled by the web interface registered above
	// will be handled by looking for a matching file in the public/ folder.
	router.get("*", serveStaticFiles (findPublicDir ()));

	// Start up the HTTP server
	auto settings = new HTTPServerSettings;
	settings.port = 8080;
	settings.bindAddresses = ["::1", "127.0.0.1"];
	settings.sessionStore = new MemorySessionStore;
	listenHTTP (settings, router);

	logInfo("Please open http://127.0.0.1:8080/ in your browser.");
}
