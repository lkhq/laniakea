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
public import laniakea.db.lkid : LkId, LkidType;

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
struct SourcePackage
{
    LkId lkid;
    PackageType type = PackageType.SOURCE;

    string name;       /// Source package name
    string ver;        /// Version of this package
    string suite;      /// Suite this package is in
    string component;  /// Component this package is in

    string repository; /// The archive this package is part of

    string[] architectures;
    PackageInfo[] binaries;

    string standardsVersion;
    string format;

    string homepage;
    string vcsBrowser;

    string maintainer;
    string[] uploaders;

    string[] buildDepends;
    ArchiveFile[] files;
    string directory;


    import laniakea.db.database : PgRow, unpackRowValues;
    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &name,
                 &ver,
                 &suite,
                 &component,
                 &repository,
                 &architectures,
                 &binaries,
                 &standardsVersion,
                 &format,
                 &homepage,
                 &vcsBrowser,
                 &maintainer,
                 &uploaders,
                 &buildDepends,
                 &files,
                 &directory
        );
    }
}

/**
 * Data of a binary package.
 */
struct BinaryPackage
{
    LkId lkid;
    PackageType type = PackageType.BINARY;

    DebType debType;   /// Deb package type
    string name;       /// Package name
    string ver;        /// Version of this package
    string suite;      /// Suite this package is in
    string component;  /// Component this package is in

    string repository; /// Name of the archive this package is part of

    string architecture;
    int    installedSize; /// Size of the installed package (an int instead of e.g. ulong for now for database reasons)

    string description;
    string descriptionMd5;

    string sourceName;
    string sourceVersion;

    PackagePriority priority;
    string section;

    string[] depends;
    string[] preDepends;

    string maintainer;

    ArchiveFile file;

    string homepage;


    import laniakea.db.database : PgRow, unpackRowValues;
    this (PgRow r) @trusted
    {
        r.unpackRowValues (
                 &lkid,
                 &name,
                 &ver,
                 &suite,
                 &component,
                 &debType,
                 &repository,
                 &architecture,
                 &installedSize,
                 &description,
                 &descriptionMd5,
                 &sourceName,
                 &sourceVersion,
                 &priority,
                 &section,
                 &depends,
                 &preDepends,
                 &maintainer,
                 &file,
                 &homepage
        );
    }
}
