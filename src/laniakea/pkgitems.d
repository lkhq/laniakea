/*
 * Copyright (C) 2016-2017 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.pkgitems;
@safe:
public import std.uuid : UUID;

import laniakea.db.utils;
import laniakea.db.schema.core;

/**
 * Type of the package.
 */
enum PackageType
{
    UNKNOWN,
    SOURCE,
    BINARY
}

/**
 * Type of the Debian archive item.
 */
enum DebType
{
    UNKNOWN,
    DEB,
    UDEB
}

/**
 * Convert the text representation into the enumerated type.
 */
DebType debTypeFromString (string str) pure
{
    if (str == "deb")
        return DebType.DEB;
    if (str == "udeb")
        return DebType.UDEB;
    return DebType.UNKNOWN;
}

/**
 * Priority of a Debian package.
 */
enum PackagePriority
{
    UNKNOWN,
    REQUIRED,
    IMPORTANT,
    STANDARD,
    OPTIONAL,
    EXTRA
}

/**
 * Convert the text representation into the enumerated type.
 */
PackagePriority packagePriorityFromString (string str) pure
{
    if (str == "optional")
        return PackagePriority.OPTIONAL;
    if (str == "extra")
        return PackagePriority.EXTRA;
    if (str == "standard")
        return PackagePriority.STANDARD;
    if (str == "important")
        return PackagePriority.IMPORTANT;
    if (str == "required")
        return PackagePriority.REQUIRED;

    return PackagePriority.UNKNOWN;
}

/**
 * Priority of a package upload.
 */
enum VersionPriority
{
    LOW,
    MEDIUM,
    HIGH,
    CRITICAL,
    EMERGENCY
}

string toString (VersionPriority priority)
{
    switch (priority) {
        case VersionPriority.LOW:
            return "low";
        case VersionPriority.MEDIUM:
            return "medium";
        case VersionPriority.HIGH:
            return "high";
        case VersionPriority.CRITICAL:
            return "critical";
        case VersionPriority.EMERGENCY:
            return "emergency";
        default:
            return "unknown";
    }
}

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
 * Basic package information, used by
 * SourcePackage to refer to binary packages.
 */
struct PackageInfo
{
    DebType debType;
    string name;
    string ver;

    string section;
    PackagePriority priority;
    string[] architectures;
}

/**
 * Data of a source package.
 */
class SourcePackage
{
    mixin UUIDProperty;

    string name;       /// Source package name
    @Column ("version") string ver; /// Version of this package
    string suite;      /// Suite this package is in
    string component;  /// Component this package is in

    string repository; /// The archive this package is part of

    string[] architectures;
    mixin (JsonDatabaseField!("architectures", "architectures", "string[]"));
    PackageInfo[] binaries;
    mixin (JsonDatabaseField!("binaries", "binaries", "PackageInfo[]"));

    string standardsVersion;
    string format;

    string homepage;
    string vcsBrowser;

    string maintainer;
    string[] uploaders;
    mixin (JsonDatabaseField!("uploaders", "uploaders", "string[]"));

    string[] buildDepends;
    mixin (JsonDatabaseField!("buildDepends", "buildDepends", "string[]"));

    ArchiveFile[] files;
    mixin (JsonDatabaseField!("files", "files", "ArchiveFile[]"));
    string directory;

    void ensureUUID (bool regenerate = false)
    {
        import std.uuid : sha1UUID;
        import std.array : empty;
        if (this.uuid.empty && !regenerate)
            return;

        if (this.repository.empty)
            this.repository = "master";
        this.uuid = sha1UUID (this.repository ~ "::" ~ this.name ~ "/" ~ this.ver);
    }
}

/**
 * Data of a binary package.
 */
class BinaryPackage
{
    mixin UUIDProperty;

    DebType debType;   /// Deb package type
    mixin (EnumDatabaseField! ("deb_type", "debType", "DebType", true));

    string name;       /// Package name
    @Column ("version") string ver; /// Version of this package
    string suite;      /// Suite this package is in
    string component;  /// Component this package is in

    string repository; /// Name of the archive this package is part of

    ArchiveArchitecture architecture;
    int    installedSize; /// Size of the installed package (an int instead of e.g. ulong for now for database reasons)

    string description;
    string descriptionMd5;

    string sourceName;
    string sourceVersion;

    PackagePriority priority;
    mixin (EnumDatabaseField! ("priority", "priority", "PackagePriority", true));

    string section;

    string[] depends;
    mixin (JsonDatabaseField! ("depends", "depends", "string[]"));

    string[] preDepends;
    mixin (JsonDatabaseField! ("preDepends", "preDepends", "string[]"));

    string maintainer;

    ArchiveFile file;
    mixin (JsonDatabaseField! ("file", "file", "ArchiveFile"));

    string homepage;

    void ensureUUID (bool regenerate = false)
    {
        import std.uuid : sha1UUID;
        import std.array : empty;
        if (this.uuid.empty && !regenerate)
            return;

        if (this.repository.empty)
            this.repository = "master";
        this.uuid = sha1UUID (this.repository ~ "::" ~ this.name ~ "/" ~ this.ver);
    }
}
