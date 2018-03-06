/*
 * Copyright (C) 2017-2018 Matthias Klumpp <matthias@tenstral.net>
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

module swview.buildsview;

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

@path("/builds")
final class BuildsView {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;
        SessionFactory sFactory;

        immutable jobsPerPage = 50;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;
        sFactory = db.newSessionFactory ();
    }

    @path("/package/:uuid/:page/")
    void getBuildsList (HTTPServerRequest req, HTTPServerResponse res)
    {
        import std.math : ceil;
        import laniakea.utils : safeParseUUID;

        auto triggerUuidStr = req.params["uuid"];
        auto triggerUuid = safeParseUUID (triggerUuidStr);
        uint currentPage = 1;
        immutable pageStr = req.params.get ("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        auto session = sFactory.openSession ();
        scope (exit) session.close ();
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        immutable jobsCount = conn.countJobsByTrigger (triggerUuid);
        immutable pageCount = ceil (jobsCount.to!real / jobsPerPage.to!real);

        auto pkgs = session.createQuery ("FROM SourcePackage
                                          WHERE sourceUUID_s=:triggerUuid
                                          ORDER BY ver")
                           .setParameter("triggerUuid", triggerUuidStr).list!SourcePackage;
        if (pkgs.length <= 0)
            return; // This should never happen
        auto sourcePkg = pkgs[0];
        auto jobs = conn.getJobsByTrigger (triggerUuid, jobsPerPage, (currentPage - 1) * jobsPerPage);

        render!("builds/builds.dt", ginfo, sourcePkg, jobs, pageCount, currentPage);
    }

    @path("/job/:uuid")
    void getJobDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        import laniakea.utils : safeParseUUID;

        auto jobUuidStr = req.params["uuid"];
        auto jobUuid = safeParseUUID (jobUuidStr);

        auto session = sFactory.openSession ();
        scope (exit) session.close ();
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto job = conn.getJobById (jobUuidStr);
        if (job.isNull)
            return; // 404

        auto pkgs = session.createQuery ("FROM SourcePackage
                                          WHERE sourceUUID_s=:triggerUuid
                                          ORDER BY ver")
                           .setParameter("triggerUuid", job.trigger.toString).list!SourcePackage;
        if (pkgs.length <= 0)
            return; // This should never happen
        auto sourcePkg = pkgs[0];

        auto workerName = conn.getJobWorkerName (job);

        render!("builds/build_details.dt", ginfo, sourcePkg, job, workerName);
    }
}
