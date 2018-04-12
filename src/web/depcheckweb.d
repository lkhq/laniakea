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

module web.depcheckweb;

import std.exception : enforce;
import std.array : empty;
import std.conv : to;
import vibe.core.log;
import vibe.http.router;
import vibe.http.server;
import vibe.utils.validation;
import vibe.web.web;
import containers : HashMap;

import laniakea.db;

import web.webconfig;

@path("/depcheck")
class DepcheckWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;

        immutable issuesPerPage = 100;
        HashMap!(string, ArchiveSuite) suitesMap;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;

        foreach (ref s; ginfo.suites)
            suitesMap[s.name] = s;
    }

    @path(":suite/:type/:arch/:page")
 	void getIssueList (HTTPServerRequest req, HTTPServerResponse res)
 	{
        import std.math : ceil;
        import std.range : take;

        immutable suiteName = req.params.get ("suite");
        immutable packageKindStr = req.params.get ("type");
        immutable archName = req.params.get ("arch");
        PackageType packageKind;
        if (packageKindStr == "binary")
            packageKind = PackageType.BINARY;
        else if (packageKindStr == "source")
            packageKind = PackageType.SOURCE;
        else
            return; // Not found

        auto suite = suitesMap.get (suiteName, null);
        if (suite is null)
            return; // Not found

        uint currentPage = 1;
        immutable pageStr = req.params.get ("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        auto sFactory = db.newSessionFactory! (DebcheckIssue);
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        auto q = session.createQuery ("FROM DebcheckIssue
                                       WHERE suiteName=:suite
                                         AND packageKind_i=:kind
                                         AND architecture=:arch
                                       ORDER BY packageName")
                        .setParameter ("suite", suiteName)
                        .setParameter ("kind", packageKind.to!short)
                        .setParameter ("arch", archName);

        // FIXME: Hibernated doesn't seem to support LIMIT/OFFSET...
        const allIssues = q.list!DebcheckIssue;
        immutable issuesCount = allIssues.length;
        immutable pageCount = ceil (issuesCount.to!real / issuesPerPage.to!real);

        const DebcheckIssue[] issues = issuesCount > 0? allIssues[(currentPage - 1) * issuesPerPage .. $].take (issuesPerPage) : [];

        render!("depcheck/issues.dt", ginfo,
                suite, packageKind, issues,
                pageCount, currentPage);
 	}

    @path(":suite/:type/:arch")
    void getIssueListPageOne (HTTPServerRequest req, HTTPServerResponse res)
 	{
        res.redirect (req.params["arch"] ~ "/1");
    }

    @path("details/:suite/:type/:packageName/:packageVersion")
 	void getDependencyIssueDetails (HTTPServerRequest req, HTTPServerResponse res)
 	{
        immutable suiteName = req.params.get("suite");
        immutable packageName = req.params.get("packageName");
        immutable packageVersion = req.params.get("packageVersion");
        immutable packageKindStr = req.params.get("type");
        PackageType packageKind;
        if (packageKindStr == "binary")
            packageKind = PackageType.BINARY;
        else if (packageKindStr == "source")
            packageKind = PackageType.SOURCE;
        else
            return; // Not found

        auto sFactory = db.newSessionFactory! (DebcheckIssue);
        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        const issue = session.createQuery ("FROM DebcheckIssue
                                       WHERE suiteName=:suite
                                         AND packageKind_i=:kind
                                         AND packageName=:pkgname
                                         AND packageVersion=:version")
                             .setParameter("suite", suiteName)
                             .setParameter("kind", packageKind.to!short)
                             .setParameter("pkgname", packageName)
                             .setParameter("version", packageVersion)
                             .uniqueResult!DebcheckIssue;
        if (issue is null)
            return;

        render!("depcheck/issue-details.dt", ginfo, suiteName, packageKind, issue);
 	}

}
