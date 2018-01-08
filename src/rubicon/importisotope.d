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

module rubicon.importisotope;
@safe:

import std.conv : to;
import std.array : empty, replace;
import std.string : strip, format, endsWith;
import std.path : buildPath, baseName;
import vibe.data.bson;

import laniakea.db;
import laniakea.logging;

import rubicon.rubiconfig;
import rubicon.fileimport;


public void handleIsotopeUpload (RubiConfig conf, DudData dud, Job job) @trusted
{
    import std.file;
    auto db = Database.get;
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    string resultMoveTo;
    const recipe = conn.getRecipeById (job.trigger);
    if (!recipe.isNull) {
        resultMoveTo = recipe.resultMoveTo;
    }

    immutable imageDirTmpl = buildPath (conf.isotopeRootDir, resultMoveTo).strip;
    if (imageDirTmpl.empty) {
        logError ("Found an Isotope ISO image build, but we have no idea where to put it. Is 'IsotopeRootDir' set correctly?");
        return;
    }

    immutable imageDir = imageDirTmpl.replace ("%{DATETIME}", dud.date.toISOExtString)
                                     .replace ("%{DATE}", "%02d-%02d-%02d".format (dud.date.year, dud.date.month, dud.date.day))
                                     .replace ("%{TIME}", "%02d.%02d".format (dud.date.hour, dud.date.minute));
    mkdirRecurse (imageDir);

    // move the image build artifacts
    foreach (ref af; dud.files) {
        if (af.fname.endsWith (".log"))
            continue; // logs are handled already by the generic tool

        immutable targetFname = buildPath (imageDir, af.fname.baseName);
        af.fname.safeRename (targetFname);
    }
}
