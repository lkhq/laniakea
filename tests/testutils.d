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
import std.string : format;

@safe:

/**
 * Print a test name to stdout.
 * Useful for long running tests, to see which test is running at time.
 */
@trusted
void printTestInfo (string, Args...) (const string tmpl, const Args args)
{
    writeln ("TEST: ", format (tmpl, args));
}

/**
 * Helper to print some helpful information when an equality assertion fails.
 */
@trusted
void assertEq(T, U) (T t, U u, string file = __FILE__, ulong line = __LINE__)
{
    import std.conv : to;
    assert (t == u, "\n" ~ file ~ ":" ~ line.to!string ~ "  '" ~ t.to!string ~ "' != '" ~ u.to!string ~ "'");
}
