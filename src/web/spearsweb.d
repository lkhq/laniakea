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
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;

import laniakea.db;

import web.webconfig;

@path("/migration")
class SpearsWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;
 	}

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;
    }

    @path("excuses")
 	void getMigrationExcuses ()
 	{
        auto collExcuses = db.getCollection ("spears.excuses");
        auto excuses = collExcuses.find!SpearsExcuse (["sourceSuite": "unstable", "targetSuite": "testing"]);
        render!("migration/excuses.dt", ginfo, excuses);
 	}

    @path("excuses/:source/:version")
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

        render!("migration/excuse-details.dt", ginfo, excuse);
    }

}
