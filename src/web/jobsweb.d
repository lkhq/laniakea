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

module web.jobsweb;

import std.exception : enforce;
import std.conv : to;
import std.array : empty, appender;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;

import laniakea.db;

import web.webconfig;

@path("/jobs")
class JobsWebService {
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

    @path("/:job_id")
 	void getJobDetails (HTTPServerRequest req, HTTPServerResponse res)
 	{
        immutable job_id = req.params["job_id"];
        if (job_id.empty)
            return;
        if (job_id.length != 36)
            return;
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        const job = conn.getJobById (job_id);
        if (job.isNull)
            return;

        if (job.moduleName == LkModule.ISOTOPE) {
            // we have an isotope job!
            render!("jobs/details_isojob.dt", ginfo, job);
        } else {
            return; // FIXME: We need generic details for jobs that aren't treated special
        }
 	}

}
