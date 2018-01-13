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

module laniakea.db.schema.ariadne;
@safe:

/**
* Configuration specific for the Ariadne module.
**/
struct AriadneConfig {
   string indepArchAffinity; /// Architecture on which arch-indep packages should be built
}

import laniakea.db.database;

/**
 * Add/update configuration.
 */
void update (Database db, AriadneConfig conf)
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    db.updateConfigEntry (conn, LkModule.ARIADNE, "indepArchAffinity", conf.indepArchAffinity);
}

auto getAriadneConfig (Database db)
{
    import std.array : empty;
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    AriadneConfig conf;
    conf.indepArchAffinity = db.getConfigEntry!string (conn, LkModule.ARIADNE, "indepArchAffinity");

    // assume amd64 as architecture to build arch-indep packages on by default
    if (conf.indepArchAffinity.empty)
        conf.indepArchAffinity = "amd64";

    return conf;
}
