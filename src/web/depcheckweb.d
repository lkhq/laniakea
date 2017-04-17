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
import vibe.db.mongo.mongo;

import laniakea.db;

import web.webconfig;

@path("/depcheck")
class DepcheckWebService {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;

        immutable issuesPerPage = 50;
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
        import vibe.data.bson;
        import std.math : ceil;

        immutable suiteName = req.params.get("suite");
        immutable packageKindStr = req.params.get("type");
        PackageKind packageKind;
        if (packageKindStr == "binary")
            packageKind = PackageKind.BINARY;
        else if (packageKindStr == "source")
            packageKind = PackageKind.SOURCE;
        else
            return; // Not found

        uint currentPage = 1;
        immutable pageStr = req.params.get("page");
        if (!pageStr.empty) {
            try {
                currentPage = pageStr.to!int;
            } catch {
                return; // not an integer, we can't continue
            }
        }

        auto query = ["suiteName": Bson(suiteName), "packageKind": Bson(packageKind.to!int)];
        auto collIssues = db.getCollection! (LkModule.DEBCHECK, "issues");

        auto pageCount = ceil (collIssues.count (query).to!real / issuesPerPage.to!real);
        auto issues = collIssues.find!(DebcheckIssue) (query, null,
                                                       QueryFlags.None,
                                                       (currentPage - 1) * issuesPerPage).limit (issuesPerPage);

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
        import vibe.data.bson;
        immutable suiteName = req.params.get("suite");
        immutable packageName = req.params.get("packageName");
        immutable packageVersion = req.params.get("packageVersion");
        immutable packageKindStr = req.params.get("type");
        PackageKind packageKind;
        if (packageKindStr == "binary")
            packageKind = PackageKind.BINARY;
        else if (packageKindStr == "source")
            packageKind = PackageKind.SOURCE;
        else
            return; // Not found

        auto collIssues = db.getCollection! (LkModule.DEBCHECK, "issues");
        auto issue = collIssues.findOne!DebcheckIssue (["suiteName": Bson(suiteName),
                                                        "packageKind": Bson(cast(int) packageKind),
                                                        "packageName": Bson(packageName),
                                                        "packageVersion": Bson(packageVersion)]);
        if (issue.isNull)
            return;

        render!("depcheck/issue-details.dt", ginfo, suiteName, packageKind, issue);
 	}

}
