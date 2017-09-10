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

import vibe.db.mongo.mongo;
import vibe.data.serialization : name;
import laniakea.db.schema.jobs;
import laniakea.db.schema.core;

alias mongoName = name;


/**
 * Instructions on how to do an automatic ISO image build.
 */
struct ImageBuildRecipe {
    @mongoName("_id") BsonObjectID id;

    string name;            /// A unique name identifying this recipe
    string distribution;    /// Name of the distribution, e.g. "Tanglu"
    string suite;           /// Suite of the distribution to build an image for
    string flavor;          /// The flavor to build
    string[] architectures; /// Architectures to build the image for

    string liveBuildGit;    /// Git repository URL with the live-build scripts
    string resultMoveTo;    /// Local or remote URL to copy the resulting build artifacts to
}

/**
 * A job containing an iso-image build task.
 */
struct ImageBuildJob {
    mixin Job!(LkModule.ISOTOPE, "image-build");

    string distribution;  /// Name of the distribution, e.g. "Tanglu"
    string suite;         /// Suite of the distribution to build an image for
    string flavor;        /// The flavor to build
    string architecture;  /// The architecture to build the image for

    string liveBuildGit;  /// Git repository URL with the live-build scripts
}
