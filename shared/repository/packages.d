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

module laniakea.packages;


/**
 * A file in the archive.
 */
struct ArchiveFile
{
    /// the filename of the file
    string fname;
    /// the size of the file
    size_t size;
    /// the files' checksum
    string sha256sum;
}

/**
 * Data of a source package.
 */
struct SourcePackage
{
    string name;
    string ver;
    string[] architectures;
    string[] binaryNames;

    string standardsVersion;
    string format;

    string vcsBrowser;

    string maintainer;
    string[] uploaders;

    string[] buildDepends;
    ArchiveFile[] files;
    string directory;
}

/**
 * Data of a binary package.
 */
struct BinaryPackage
{
    string name;
    string ver;
    string architecture;

    string priority;
    string section;

    string[] depends;
    string[] preDepends;

    string maintainer;
    string[] uploaders;

    ArchiveFile file;

    string homepage;
}
