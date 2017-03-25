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

import testutils;
import spears.excuses;

void testExcusesFile (const string datadir)
{
    import std.path : buildPath;
    import std.stdio : writeln;

    printTestInfo ("Spears.Excuses");

    immutable excusesFname = buildPath (datadir, "spears", "excuses.yml");

    auto ef = new ExcusesFile (excusesFname, "testSource", "testTarget");

    ef.getExcuses ();

static if (0) {
    import laniakea.db;
    import laniakea.localconfig;
    LocalConfig.get.load (LkModule.SPEARS);
    auto db = Database.get;
    auto collExcuses = db.getCollection ("spears.excuses");
    foreach (cur; collExcuses.find (["sourceSuite": "testSource", "targetSuite": "testTarget"]))
        collExcuses.remove (cur);
    foreach (excuse; ef.getExcuses ().byValue) {
        excuse.id = db.newBsonId ();
        collExcuses.insert (excuse);
    }
}

}
