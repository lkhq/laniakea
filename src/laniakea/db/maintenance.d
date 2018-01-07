/*
 * Copyright (C) 2017-2018 Matthias Klumpp <matthias@tenstral.net>
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

import laniakea.db.database;


/**
 * Call functions on a module with this database as parameter.
 */
private void callSchemaFunction (string fun, string mod_name) (Database db)
{
    static import laniakea.db.schema;

    mixin("alias mod = laniakea.db.schema." ~ mod_name ~ ";");

    foreach (m; __traits (derivedMembers, mod))
    {
        static if (__traits(isStaticFunction, __traits (getMember, mod, m)))
            static if (m == fun)
                __traits (getMember, mod, m) (db);
    }
}

/**
 * Create database and all tables
 */
void initializeDatabase (Database db)
{
    import laniakea.db.schema : __laniakea_db_schema_names;

    // ensure we have the debversion extension loaded for this database
    db.simpleExecute ("CREATE EXTENSION IF NOT EXISTS debversion;");

    foreach (ref schemaMod; __laniakea_db_schema_names)
    {
        callSchemaFunction! ("createTables", schemaMod) (db);
    }
}
