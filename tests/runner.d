/*
 * Copyright (C) 2016 Matthias Klumpp <matthias@tenstral.net>
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

import std.stdio : writeln;
import core.stdc.stdlib : exit;
import std.path : buildPath;
static import std.file;

// import test units
import repotests;
import gpgtests;

import fluent.asserts;

//! static import test_spears;

import laniakea.localconfig;
import laniakea.logging;

void main (string[] args)
{
    if (args.length != 2) {
        writeln ("That's planning for failure, Morty. Even dumber than regular planning.");
        writeln ("(You should really pass a directory with test data as first parameter.)");
        exit (1);
    }

    immutable testDataDir = args[1];
    if (!std.file.exists (testDataDir)) {
        writeln ("Glurp... Test data directory ", testDataDir, " does not exist, something is really wrong here...");
        exit (1);
    }

    // go verbose unconditionally
    setVerboseLog (true);

    // set up the global configuration
    auto conf = LocalConfig.get;
    conf.loadFromFile (buildPath (testDataDir, "config", "base-config.json"), LkModule.TESTSUITE);

    // test the local configuration
    conf.cacheDir.should.equal ("/var/tmp/laniakea");
    conf.workspace.should.equal ("/tmp/test-lkws/");

    conf.databaseHost.should.equal ("localhost");
    conf.databasePort.should.equal (5432);
    conf.databaseName.should.equal ("laniakea_test");
    conf.databaseUser.should.equal ("lkdbuser_test");
    conf.databasePassword.should.equal ("notReallySecret");
    conf.databaseExtraOpts.should.equal ("");

    conf.lighthouseEndpoint.should.equal ("tcp://*:5570");

    // add the trusted keyring with test keys
    conf.trustedGpgKeyrings ~= buildPath (testDataDir, "gpg", "keyrings", "keyring.gpg");
    conf.trustedGpgKeyrings ~= buildPath (testDataDir, "gpg", "keyrings", "other-keyring.gpg");

    // initialize the database
    import laniakea.db.database : Database;
    import laniakea.db.maintenance : initializeDatabase;
    auto db = Database.get;
    db.initializeDatabase ();

    // At this point, we already ran all the stuff from unittest blocks.
    // now we can do a bit more complex tests which are longer or
    // involve a lot of pieces needing to work well together.
    // Those tests also only test public API, and usually require
    // aditional data from the test-data directory (while stuff in
    // unittest blocks is always standalone).
    testRepositoryRead (testDataDir);

    testArchiveDatabase (testDataDir);

    testGnuPG (testDataDir);

    // Spears
    //! test_spears.testExcusesFile (testDataDir);

    writeln ("Done.");
}
