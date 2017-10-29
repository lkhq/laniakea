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
import laniakea.pkgitems;

import webswview.webconfig;

@path("/package")
final class PackageView {
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

    @path("/:type/:suite/:component/:name")
    void getPackageDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        auto type = req.params["type"];
        auto suite = req.params["suite"];
        auto component = req.params["component"];
        auto pkgName = req.params["name"];

        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        if (type == "binary") {
            auto pkgs = conn.getBinaryPackageVersions ("master", suite, component, pkgName);
            if (pkgs.length <= 0)
                return;
            auto pkg = pkgs[0];

            render!("pkgview/details_binary.dt", ginfo, pkg);
            return;

        } else if (type == "source") {
            auto pkgs = conn.getSourcePackageVersions ("master", suite, component, pkgName);
            if (pkgs.length <= 0)
                return;
            auto pkg = pkgs[0];

            render!("pkgview/details_source.dt", ginfo, pkg);
            return;

        } else {
            return; // 404
        }
    }
}
