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
        SessionFactory sFactory;

        immutable jobsPerPage = 50;
        struct JobInfo {
            string uuid;
            string title;

            JobStatus status;
            string architecture;
            DateTime createdTime;
            int priority;
        }
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;

        sFactory = db.newSessionFactory ();
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
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        const job = conn.getJobById (job_id);
        if (job.isNull)
            return;

        auto workerName = conn.getJobWorkerName (job);

        if (job.kind == JobKind.PACKAGE_BUILD) {
            // we have an Ariadne package build job!
            auto spkg = session.getSourcePackageForJob (job.get);
            if (spkg is null) {
                spkg = new SourcePackage;
                spkg.name = "Unknown";
                spkg.ver = "?";
            }

            render!("jobs/details_packagejob.dt", ginfo, job, workerName, spkg);
        } else if (job.kind == JobKind.OS_IMAGE_BUILD) {
            // we have an Isotope image build job!
            auto recipe = conn.getRecipeById (job.trigger);
            if (!recipe.isNull) {
                recipe = ImageBuildRecipe ();
                recipe.name = "Unknown";
                recipe.distribution = "?";
            }

            render!("jobs/details_isojob.dt", ginfo, job, workerName, recipe);
        } else {
            render!("jobs/details_generic.dt", ginfo, job, workerName);
        }
 	}

    static private string makeJobTitle (Connection conn, laniakea.db.database.Session session, ref Job job)
    {
        import std.string : format;

        if (job.kind == JobKind.PACKAGE_BUILD) {
            auto spkg = session.getSourcePackageForJob (job);
            if (spkg is null)
                return "? Unknown package build";
            return "Package build: %s/%s".format (spkg.name, spkg.ver);

        } else if (job.kind == JobKind.PACKAGE_BUILD) {
            auto recipe = conn.getRecipeById (job.trigger);
            if (recipe.isNull)
                return "? Unknown OS image build";
            return "OS image build: " ~ recipe.name;
        }

        return "? Alien Job";
    }

    @path("/queue/:page")
 	void getJobQueue (HTTPServerRequest req, HTTPServerResponse res)
 	{
        import std.math : ceil;
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        uint currentPage = 1;
        immutable pageStr = req.params.get ("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        immutable jobsCount = conn.countPendingJobs ();
        immutable pageCount = ceil (jobsCount.to!real / jobsPerPage.to!real);

        auto jobs = conn.getPendingJobs (jobsPerPage, (currentPage - 1) * jobsPerPage);
        auto infoList = appender! (JobInfo[]);
        foreach (ref j; jobs) {
            JobInfo info;
            info.uuid = j.uuid.toString;
            info.status = j.status;
            info.architecture = j.architecture;
            info.createdTime = j.createdTime;
            info.priority = j.priority;
            info.title = makeJobTitle (conn, session, j);

            infoList ~= info;
        }

        auto jobInfos = infoList.data;
        render!("jobs/jobqueue.dt", ginfo, jobInfos, pageCount, currentPage);
 	}

}
