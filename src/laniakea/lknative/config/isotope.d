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

module lknative.config.isotope;
@safe:

import std.uuid : UUID;
import std.conv : to;


/**
 * Kind of the image to build.
 **/
enum ImageKind {
    UNKNOWN,
    ISO,
    IMG
}

string toString (ImageKind kind) {
    switch (kind) {
        case ImageKind.ISO: return "iso";
        case ImageKind.IMG: return "img";

        default: return "unknown";
    }
}

ImageKind imageKindFromString (string s)
{
    switch (s) {
        case "iso": return ImageKind.ISO;
        case "img": return ImageKind.IMG;

        default: return ImageKind.UNKNOWN;
    }
}

/**
 * Instructions on how to do an automatic ISO image build.
 */
struct ImageBuildRecipe {
    UUID uuid;              /// Laniakea object ID

    ImageKind kind;         /// The kind of image to build

    string name;            /// A unique name identifying this recipe
    string distribution;    /// Name of the distribution, e.g. "Tanglu"
    string suite;           /// Suite of the distribution to build an image for
    string flavor;          /// The flavor to build
    string[] architectures; /// Architectures to build the image for

    string gitUrl;          /// Git repository URL with the live-build scripts / other build recipes
    string resultMoveTo;    /// Local or remote URL to copy the resulting build artifacts to
}
