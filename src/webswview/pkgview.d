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

module swview.pkgview;

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
        sFactory = db.newSessionFactory! (SpearsExcuse);
    }

    private auto getMigrationExcusesFor (HibernatedSession session, string sourceSuite, string sourcePackage, string newVersion)
    {
        const excuses = session.createQuery ("FROM SpearsExcuse
                                              WHERE sourceSuite=:srcSuite
                                                AND sourcePackage=:srcPkgname
                                                AND newVersion=:version")
                              .setParameter("srcSuite", sourceSuite)
                              .setParameter("srcPkgname", sourcePackage)
                              .setParameter("version", newVersion)
                              .list!SpearsExcuse;

        return excuses;
    }

    @path("/:type/:suite/:component/:name")
    void getPackageDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        auto type = req.params["type"];
        auto currentSuite = req.params["suite"];
        auto component = req.params["component"];
        auto pkgName = req.params["name"];

        auto session = sFactory.openSession ();
        scope (exit) session.close ();
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        if (type == "binary") {
            auto q = session.createQuery ("FROM BinaryPackage
                                              WHERE repo.name=:repoName
                                                AND component.name=:componentName
                                                AND name=:pkgName
                                              ORDER BY ver")
                               .setParameter("repoName", "master")
                               .setParameter("componentName", component)
                               .setParameter("pkgName", pkgName);
            BinaryPackage pkg = null;
            foreach (p; q.list!BinaryPackage) {
                foreach (s; p.suites) {
                    if (s.name == currentSuite) {
                        pkg = p;
                        break;
                    }
                }
            }
            if (pkg is null)
                return; // 404

            auto suites = conn.getPackageSuites!BinaryPackage ("master", component, pkgName);
            render!("pkgview/details_binary.dt", ginfo, pkg, currentSuite, suites);
            return;

        } else if (type == "source") {
            auto q = session.createQuery ("FROM SourcePackage
                                              WHERE repo.name=:repoName
                                                AND component.name=:componentName
                                                AND name=:pkgName
                                              ORDER BY ver")
                               .setParameter("repoName", "master")
                               .setParameter("componentName", component)
                               .setParameter("pkgName", pkgName);
            SourcePackage pkg = null;
            foreach (p; q.list!SourcePackage) {
                foreach (s; p.suites) {
                    if (s.name == currentSuite) {
                        pkg = p;
                        break;
                    }
                }
            }
            if (pkg is null)
                return; // 404

            // one source package may be in multiple suites
            auto suites = conn.getPackageSuites!SourcePackage ("master", component, pkgName);

            // we display migration excuses immediately on the details page at time
            auto migrationExcuses = getMigrationExcusesFor (session, currentSuite, pkgName, pkg.ver);

            render!("pkgview/details_source.dt", ginfo, pkg, currentSuite, suites, migrationExcuses);
            return;

        } else {
            return; // 404
        }
    }
}
