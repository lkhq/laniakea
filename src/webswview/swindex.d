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

module swview.swindex;

import std.exception : enforce;
import std.conv : to;
import std.array : empty, appender;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;

import laniakea.db;
import laniakea.db.schema.archive;

import webswview.webconfig;

final class SWWebIndex {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        ginfo = wconf.ginfo;
        db = wconf.db;
    }

	// overrides the path that gets inferred from the method name to
	// "GET /"
	@path("/")
    void getHome()
	{
		render!("home.dt", ginfo);
	}

    @method(HTTPMethod.GET) @path("/search")
 	void getPackageSearch (HTTPServerRequest req, HTTPServerResponse res)
 	{
        immutable searchTerm = req.query["term"];
        if (searchTerm.empty)
            return;

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto results = conn.findBinaryPackage ("master", searchTerm);

        // FIXME: Combine the data and make it easier to use
        render!("search_results.dt", ginfo, results, searchTerm);
 	}
}
