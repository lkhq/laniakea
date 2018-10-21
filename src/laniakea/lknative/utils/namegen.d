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

module lknative.utils.namegen;

import std.string : splitLines, format;
import std.random : dice, rndGen, uniform;

/**
 * Newer Phobos versions have std.random.choice, but we want to be
 * compatible here.
 */
private auto ref choice(const(string[]) range)
{
    import std.conv : to;

    return range[uniform(to!size_t(0), $, rndGen)];
}

enum RandomNameStyle {
    RANDOM,
    ANIMAL
}

/**
 * Generate a random name that is easy for humans to remember.
 * These names should be used for entities which are not transient
 * and which humans likely want to refer to often (such as e.g. worker machines)
 */
public string generateName (RandomNameStyle style = RandomNameStyle.RANDOM)
{
    static immutable adjectives = import("words/adjectives.txt").splitLines();
    static immutable mixedNouns = import("words/nouns.txt").splitLines();
    static immutable intermediate = import("words/intermediate.txt").splitLines();
    static immutable animals = import("words/animals.txt").splitLines();

    immutable nouns = (style == RandomNameStyle.ANIMAL)? animals : mixedNouns;

    string res;
    // do we add an intermediate string? (only with a 30% chance)
    if (dice (70, 30) == 1)
        res = "%s-%s-%s".format (choice (adjectives), choice (intermediate), choice (nouns));
    else
        res = "%s-%s".format (choice (adjectives), choice (nouns));

    return res;
}
