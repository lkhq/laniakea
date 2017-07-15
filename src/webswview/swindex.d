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
import vibe.db.mongo.mongo;
import vibe.web.web;

import laniakea.db;
import laniakea.pkgitems;

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
 	void getJobDetails (HTTPServerRequest req, HTTPServerResponse res)
 	{
        immutable search_term = req.query["term"];
        if (search_term.empty)
            return;

        auto coll = db.collRepoPackages;

        auto termRE = Bson(["$regex": Bson(".*" ~ search_term ~ ".*")]);
        auto searchCur = coll.find!BinaryPackage (["type": Bson(cast(int)PackageType.BINARY),
                                                   "$or": Bson([
                                                              Bson([ "name":  termRE]),
                                                              Bson([ "description": termRE ])
                                                              ])
                                                  ]);


        // FIXME: Combine the data and make it easier to use
        auto results = searchCur;
        render!("search_results.dt", ginfo, results, search_term);
 	}
}
