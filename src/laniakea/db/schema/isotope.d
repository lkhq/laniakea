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

module laniakea.db.schema.isotope;
@safe:

import laniakea.db.schema.jobs;
import laniakea.db.schema.core;


/**
 * Instructions on how to do an automatic ISO image build.
 */
struct ImageBuildRecipe {
    LkId lkid;              /// Laniakea object ID

    string name;            /// A unique name identifying this recipe
    string distribution;    /// Name of the distribution, e.g. "Tanglu"
    string suite;           /// Suite of the distribution to build an image for
    string flavor;          /// The flavor to build
    string[] architectures; /// Architectures to build the image for

    string liveBuildGit;    /// Git repository URL with the live-build scripts
    string resultMoveTo;    /// Local or remote URL to copy the resulting build artifacts to


    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &name,
                 &distribution,
                 &suite,
                 &flavor,
                 &architectures,
                 &liveBuildGit,
                 &resultMoveTo
        );
    }
}

/**
 * A job containing an iso-image build task.
 */
struct ImageBuildJob {
    mixin Job!(LkModule.ISOTOPE, "image-build");

    struct Data {
        string distribution;  /// Name of the distribution, e.g. "Tanglu"
        string suite;         /// Suite of the distribution to build an image for
        string flavor;        /// The flavor to build
        string architecture;  /// The architecture to build the image for

        string liveBuildGit;  /// Git repository URL with the live-build scripts
    }

    Data data;
    alias data this;
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);

    conn.exec (
        "CREATE TABLE IF NOT EXISTS isotope_recipes (
          lkid VARCHAR(32) PRIMARY KEY,
          name             TEXT NOT NULL UNIQUE,
          distribution     TEXT NOT NULL,
          suite            TEXT NOT NULL,
          flavor           TEXT,
          architectures    JSONB,
          livebuild_git    TEXT NOT NULL,
          result_move_to   TEXT
        )"
    );
}

/**
 * Add/update image build recipe.
 */
void update (PgConnection conn, ImageBuildRecipe recipe) @trusted
{
    QueryParams p;
    p.sqlCommand = "INSERT INTO isotope_recipes
                    VALUES ($1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6::jsonb,
                            $7,
                            $8
                        )
                    ON CONFLICT (lkid) DO UPDATE SET
                      name           = $2,
                      distribution   = $3,
                      suite          = $4,
                      flavor         = $5,
                      architectures  = $6::jsonb,
                      livebuild_git  = $7,
                      result_move_to = $8";

    p.setParams (recipe.lkid,
                 recipe.name,
                 recipe.distribution,
                 recipe.suite,
                 recipe.flavor,
                 recipe.architectures,
                 recipe.liveBuildGit,
                 recipe.resultMoveTo
    );
    conn.execParams (p);
}

auto getBuildRecipes (PgConnection conn, long limit, long offset = 0) @trusted
{
    QueryParams p;

    if (limit > 0) {
        p.sqlCommand = "SELECT * FROM isotope_recipes LIMIT $1 OFFSET $2 ORDER BY name";
        p.setParams (limit, offset);
    } else {
        p.sqlCommand = "SELECT * FROM isotope_recipes OFFSET $1 ORDER BY name";
        p.setParams (offset);
    }

    auto ans = conn.execParams(p);
    return rowsTo!ImageBuildRecipe (ans);
}

auto getRecipeByName (PgConnection conn, string name) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM isotope_recipes WHERE name=$1";
    p.setParams (name);

    auto ans = conn.execParams(p);
    return rowsToOne!ImageBuildRecipe (ans);
}

auto getRecipeById (PgConnection conn, LkId lkid) @trusted
{
    QueryParams p;
    p.sqlCommand = "SELECT * FROM isotope_recipes WHERE lkid=$1";
    p.setParams (lkid);

    auto ans = conn.execParams(p);
    return rowsToOne!ImageBuildRecipe (ans);
}
