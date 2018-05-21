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

    struct PackageSection {
        string name;
    }

    GlobalInfo ginfo;
    PackageSection[] pkgSections;

    private {
        WebConfig wconf;
        Database db;
        SessionFactory sFactory;
    }

    this (WebConfig conf)
    {
        import laniakea.utils : readJsonFile;
        import laniakea.localconfig : getDataFile;

        wconf = conf;
        ginfo = wconf.ginfo;
        db = wconf.db;
        sFactory = db.newSessionFactory ();

        // fetch the location of the Brithey git repository from static data
        auto jroot = readJsonFile (getDataFile ("archive-sections.json"));
        auto pkgSecAppender = appender!(PackageSection[]);
        foreach (ref jsec; jroot) {
            PackageSection sec;
            sec.name = jsec["name"].to!string;
            pkgSecAppender ~= sec;
        }
        pkgSections = pkgSecAppender.data;
    }

	@path("/")
    void getHome ()
	{
		render!("home.dt", ginfo);
	}

    @method(HTTPMethod.GET) @path("/search")
 	void getPackageSearch (HTTPServerRequest req, HTTPServerResponse res)
 	{
        immutable searchTerm = req.query["term"];
        if (searchTerm.empty)
            return;

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto q = session.createQuery ("FROM BinaryPackage as pkg
                                       WHERE (name LIKE :term) OR (description LIKE :term)
                                       ORDER BY ver")
                        .setParameter("term", "%" ~ searchTerm ~ "%");

        auto results = q.list!BinaryPackage;

        // FIXME: Combine the data and make it easier to use
        render!("search_results.dt", ginfo, results, searchTerm);
 	}

    @path("/suites")
    void getArchiveSuites ()
	{
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto suites = session.createQuery ("FROM ArchiveSuite
                                       ORDER BY name")
                                       .list!ArchiveSuite;

		render!("archive_suites.dt", ginfo, suites, pkgSections);
	}

    @path("/suites/:suite/")
    void getPackageSections (HTTPServerRequest req)
	{
        immutable currentSuite = req.params["suite"];
        if (currentSuite.empty)
            return;

		render!("package_sections.dt", ginfo, currentSuite, pkgSections);
	}

    @path("/suites/:suite/:section/")
    void getSectionPackages (HTTPServerRequest req)
	{
        immutable currentSuite = req.params["suite"];
        immutable sectionName = req.params["section"];
        if (currentSuite.empty)
            return;
        if (sectionName.empty)
            return;

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto binPackages = session.createQuery ("FROM BinaryPackage
                                                 WHERE section=:sect
                                                 ORDER BY name")
                                  .setParameter("sect", sectionName)
                                  .list!BinaryPackage;
        immutable packageCount = binPackages.length;

		render!("section_packages.dt", ginfo, currentSuite, sectionName, packageCount);
	}
}
