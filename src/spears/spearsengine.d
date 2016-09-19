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

import std.array : empty;
import std.algorithm : canFind;
import std.path : buildPath;
import std.array : appender;
static import std.file;

import laniakea.repository;
import laniakea.repository.dak;
import laniakea.pkgitems;
import laniakea.config;
import laniakea.logging;

/**
 * Run package migrations using Britney and manage its configurations.
 */
class SpearsEngine
{

private:

    Dak dak;
    BaseConfig conf;

public:

    this ()
    {
        dak = new Dak ();
        conf = BaseConfig.get ();
    }

    bool updateConfig ()
    {
        immutable workspace = buildPath (conf.workspace, "spears");
        std.file.mkdirRecurse (workspace);

        return true;
    }

    bool runMigration (string fromSuite, string toSuite)
    {
        return true;
    }

    bool runMigration ()
    {
        return true;
    }

}
