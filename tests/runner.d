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

import std.stdio;
import core.stdc.stdlib : exit;
static import std.file;

// import test units
import repotests;
import gpgtests;

//! static import test_spears;

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

    // At this point, we already ran all the stuff from unittest blocks.
    // now we can do a bit more complex tests which are longer or
    // involve a lot of pieces needing to work well together.
    // Those tests also only test public API, and usually require
    // aditional data from the test-data directory (while stuff in
    // unittest blocks is always standalone).
    testRepositoryRead (testDataDir);

    testGnuPG (testDataDir);

    // Spears
    //! test_spears.testExcusesFile (testDataDir);

    writeln ("Done.");
}
