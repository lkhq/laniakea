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

module swview.jobsweb;

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

@path("/package")
final class PackageView {
    GlobalInfo ginfo;

    private {
        WebConfig wconf;
        Database db;
        SessionFactory sFactory;
    }

    this (WebConfig conf)
    {
        wconf = conf;
        db = wconf.db;
        ginfo = wconf.ginfo;
        sFactory = db.newSessionFactory ();
    }

    @path("/:type/:suite/:component/:name")
    void getPackageDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        auto type = req.params["type"];
        auto suite = req.params["suite"];
        auto component = req.params["component"];
        auto pkgName = req.params["name"];

        auto session = sFactory.openSession ();
        scope (exit) session.close ();

        if (type == "binary") {
            auto pkgs = session.createQuery ("FROM BinaryPackage
                                              WHERE suite.repo.name=:repoName
                                                AND suite.name=:suiteName
                                                AND component.name=:componentName
                                                AND name=:pkgName
                                              ORDER BY ver  ")
                               .setParameter("repoName", "master")
                               .setParameter("suiteName", suite)
                               .setParameter("componentName", component)
                               .setParameter("pkgName", pkgName).list!BinaryPackage;
            if (pkgs.length == 0)
                return;
            const pkg = pkgs[0];
            auto suites = session.getPackageSuites!BinaryPackage ("master", component, pkgName);
            render!("pkgview/details_binary.dt", ginfo, pkg, suites);
            return;

        } else if (type == "source") {
            auto pkgs = session.createQuery ("FROM SourcePackage
                                              WHERE suite.repo.name=:repoName
                                                AND suite.name=:suiteName
                                                AND component.name=:componentName
                                                AND name=:pkgName
                                              ORDER BY ver  ")
                               .setParameter("repoName", "master")
                               .setParameter("suiteName", suite)
                               .setParameter("componentName", component)
                               .setParameter("pkgName", pkgName).list!SourcePackage;
            if (pkgs.length == 0)
                return;
            const pkg = pkgs[0];
            auto suites = session.getPackageSuites!SourcePackage ("master", component, pkgName);
            render!("pkgview/details_source.dt", ginfo, pkg, suites);
            return;

        } else {
            return; // 404
        }
    }
}
