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

import laniakea.db;

import web.webconfig;

@path("/depcheck")
class DepcheckWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;

        immutable issuesPerPage = 100;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;
    }

    @path(":suite/:type/:page")
 	void getIssueList (HTTPServerRequest req, HTTPServerResponse res)
 	{
        import std.math : ceil;

        immutable suiteName = req.params.get("suite");
        immutable packageKindStr = req.params.get("type");
        PackageType packageKind;
        if (packageKindStr == "binary")
            packageKind = PackageType.BINARY;
        else if (packageKindStr == "source")
            packageKind = PackageType.SOURCE;
        else
            return; // Not found

        uint currentPage = 1;
        immutable pageStr = req.params.get("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch (Throwable) {
                return; // not an integer, we can't continue
            }
        }

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);
        const issuesCount = conn.countDebcheckIssues (suiteName, packageKind);

        auto pageCount = ceil (issuesCount.to!real / issuesPerPage.to!real);
        const issues = conn.getDebcheckIssues (suiteName,
                                               packageKind,
                                               null, // all architectures
                                               issuesPerPage,
                                               (currentPage - 1) * issuesPerPage);

        render!("depcheck/issues.dt", ginfo,
                suiteName, packageKind, issues,
                pageCount, currentPage);
 	}

    @path(":suite/:type")
    void getIssueListPageOne (HTTPServerRequest req, HTTPServerResponse res)
 	{
        res.redirect (req.params["type"] ~ "/1");
    }

    @path(":suite/:type/:packageName/:packageVersion")
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

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto issue = conn.getDebcheckIssue (suiteName, packageKind, packageName, packageVersion);
        if (issue.isNull)
            return;

        render!("depcheck/issue-details.dt", ginfo, suiteName, packageKind, issue);
 	}

}
