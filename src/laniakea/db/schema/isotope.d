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
    UUID uuid;              /// Laniakea object ID

    string name;            /// A unique name identifying this recipe
    string distribution;    /// Name of the distribution, e.g. "Tanglu"
    string suite;           /// Suite of the distribution to build an image for
    string flavor;          /// The flavor to build
    string[] architectures; /// Architectures to build the image for

    string liveBuildGit;    /// Git repository URL with the live-build scripts
    string resultMoveTo;    /// Local or remote URL to copy the resulting build artifacts to


    this (ResultSet r) @trusted
    {
        import vibe.data.json : parseJsonString, deserializeJson;
        assert (r.getMetaData.getColumnCount == 8);

        uuid          = UUID (r.getString (1));
        name          = r.getString (2);
        distribution  = r.getString (3);
        suite         = r.getString (4);
        flavor        = r.getString (5);
        architectures = deserializeJson!(string[]) (r.getString (6));

        liveBuildGit  = r.getString (7);
        resultMoveTo  = r.getString (8);
    }
}

/**
 * Data specific to a job containing an iso-image build task.
 */
struct ImageBuildJobData {
    string distribution;  /// Name of the distribution, e.g. "Tanglu"
    string suite;         /// Suite of the distribution to build an image for
    string flavor;        /// The flavor to build

    string liveBuildGit;  /// Git repository URL with the live-build scripts
}


import laniakea.db.database;

/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);
    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    stmt.executeUpdate (
        "CREATE TABLE IF NOT EXISTS isotope_recipes (
          uuid             UUID PRIMARY KEY,
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
void update (Connection conn, ImageBuildRecipe recipe) @trusted
{
    import vibe.data.json : serializeToJsonString;

    immutable sql = "INSERT INTO isotope_recipes
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

    auto ps = conn.prepareStatement (sql);
    scope (exit) ps.close ();

    ps.setString (1, recipe.uuid.toString);
    ps.setString (2, recipe.name);
    ps.setString (3, recipe.distribution);
    ps.setString (4, recipe.suite);
    ps.setString (5, recipe.flavor);
    ps.setString (6, recipe.architectures.serializeToJsonString);
    ps.setString (7, recipe.liveBuildGit);
    ps.setString (8, recipe.resultMoveTo);

    ps.executeUpdate ();
}

auto getBuildRecipes (Connection conn, long limit, long offset = 0) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM isotope_recipes ORDER BY name LIMIT $1 OFFSET $2");
    scope (exit) ps.close ();

    ps.setLong (1, offset);
    if (limit > 0)
        ps.setLong  (2, limit);
    else
        ps.setLong  (2, long.max);

    auto ans = ps.executeQuery ();
    return rowsTo!ImageBuildRecipe (ans);
}

auto getRecipeByName (Connection conn, string name) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM isotope_recipes WHERE name=$1");
    scope (exit) ps.close ();

    ps.setString (1, name);

    auto ans = ps.executeQuery ();
    return rowsToOne!ImageBuildRecipe (ans);
}

auto getRecipeById (Connection conn, UUID uuid) @trusted
{
    auto ps = conn.prepareStatement ("SELECT * FROM isotope_recipes WHERE uuid=$1");
    scope (exit) ps.close ();

    ps.setString (1, uuid.toString);

    auto ans = ps.executeQuery ();
    return rowsToOne!ImageBuildRecipe (ans);
}
