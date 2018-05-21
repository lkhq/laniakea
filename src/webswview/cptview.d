/*
 * Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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

module swview.cptview;

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

@path("/component")
final class ComponentView {
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

    @path("/:cid")
    void getComponentDetailsCidOnly (HTTPServerRequest req, HTTPServerResponse res)
    {

    }

    @path("/:cid/:uuid")
    void getComponentDetails (HTTPServerRequest req, HTTPServerResponse res)
    {
        immutable cid = req.params["cid"];
        immutable cptUuid = req.params["uuid"];

        auto session = sFactory.openSession ();
        scope (exit) session.close ();
        auto conn = db.getConnection ();
        scope (exit) db.dropConnection (conn);

        auto cpt = session.createQuery ("FROM SoftwareComponent
                                         WHERE cid=:cid
                                          AND  uuid_s=:uuid")
                               .setParameter("cid", cid)
                               .setParameter("uuid", cptUuid).uniqueResult!SoftwareComponent;
        if (cpt is null)
            return; // 404


        BinaryPackage[][string] binPackagesByArch;
        foreach (ref pkg; cpt.binPackages)
            binPackagesByArch[pkg.architecture.name] ~= pkg;

        render!("cptview/details.dt", ginfo, cpt, binPackagesByArch);
    }
}
