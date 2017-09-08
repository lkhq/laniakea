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

module web.spearsweb;

import std.exception : enforce;
import std.conv : to;
import std.array : empty;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.db.mongo.mongo;
import vibe.web.web;

import laniakea.db;

import web.webconfig;

@path("/migration")
class SpearsWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        MongoLegacyDatabase db;

        immutable excusesPerPage = 100;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;
    }

    @path(":from/:to/excuses/:page")
 	void getMigrationExcuses (HTTPServerRequest req, HTTPServerResponse res)
 	{
        import std.math : ceil;
        import std.range : take;
        immutable sourceSuite = req.params["from"];
        immutable targetSuite = req.params["to"];

        uint currentPage = 1;
        immutable pageStr = req.params.get("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        auto collExcuses = db.getCollection! (LkModule.SPEARS, "excuses");
        auto query = ["sourceSuite": sourceSuite, "targetSuite": targetSuite];

        auto pageCount = ceil (collExcuses.count (query).to!real / excusesPerPage.to!real);
        static struct Order { int sourcePackage; }
        auto excusesC = collExcuses.find!SpearsExcuse (query, null,
                                                      QueryFlags.None,
                                                      (currentPage - 1) * excusesPerPage)
                                                      .limit (excusesPerPage)
                                                      .sort(Order(1));

        // FIXME: Workaround, for some reason .limit () does not work here on MongoDB, could
        // be a bug in Mongo or Vibe.d (this exact same code works in DepcheckWeb, surprisingly...)
        auto excuses = excusesC.take (excusesPerPage);

        render!("migration/excuses.dt", ginfo,
                currentPage, pageCount,
                sourceSuite, targetSuite, excuses);
 	}

    @path(":from/:to/excuses")
 	void getMigrationExcusesPageOne (HTTPServerRequest req, HTTPServerResponse res)
 	{
        res.redirect ("excuses/1");
    }

    @path(":from/:to/excuses/:source/:version")
    void getMigrationExcuseDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        immutable sourceSuite = req.params["from"];
        immutable targetSuite = req.params["to"];

        immutable sourcePackage = req.params["source"];
        immutable newVersion = req.params["version"];

        auto collExcuses = db.getCollection ("spears.excuses");
        auto excuse = collExcuses.findOne!SpearsExcuse (["sourcePackage": sourcePackage, "newVersion": newVersion]);
        if (excuse.isNull) {
            res.statusCode = 404;
            res.writeBody("");
            return;
        }

        render!("migration/excuse-details.dt", ginfo, excuse);
    }

}
