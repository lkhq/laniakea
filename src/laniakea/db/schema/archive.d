/*
 * Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
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

module laniakea.db.schema.archive;
@safe:

import laniakea.db.utils;
import hibernated.core;


/**
 * A system architecture software can be compiled for.
 * Usually associated with an @ArchiveSuite
 */
class ArchiveRepository
{
    @Id @Generated
    int id;

    @UniqueKey
    string name; /// Name of the repository

    LazyCollection!ArchiveSuite suites;

    this () {}
    this (string name)
    {
        this.name = name;
    }
}

/**
 * Information about a distribution suite.
 */
class ArchiveSuite
{
    @Id @Generated
    int id;

    string name;

    ArchiveRepository repo;

    @ManyToMany
    LazyCollection!ArchiveArchitecture architectures;

    @ManyToMany
    LazyCollection!ArchiveComponent components;

    @Null
    string baseSuiteName;

    LazyCollection!BinaryPackage binPackages;
    LazyCollection!BinaryPackage srcPackages;

    this () {}
    this (string name)
    {
        this.name = name;
    }
}

/**
 * Information about a distribution component.
 */
class ArchiveComponent
{
    @Id @Generated
    int id;

    @UniqueKey
    string name;

    @ManyToMany
    LazyCollection!ArchiveSuite suites;

    string[] dependencies; /// Other components that need to be present to fulfill dependencies of packages in this component
    mixin (JsonDatabaseField! ("dependencies", "dependencies", "string[]"));

    LazyCollection!BinaryPackage binPackages;
    LazyCollection!BinaryPackage srcPackages;

    this () {}
    this (string name)
    {
        this.name = name;
    }
}

/**
 * A system architecture software can be compiled for.
 * Usually associated with an @ArchiveSuite
 */
class ArchiveArchitecture
{
    @Id @Generated
    int id;

    @UniqueKey
    string name;

    @ManyToMany
    LazyCollection!ArchiveSuite suites; /// Suites that contain this architecture

    LazyCollection!BinaryPackage binPackages;

    this () {}
    this (string name)
    {
        this.name = name;
    }
}

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
@Table("archive_src_package")
class SourcePackage
{
    mixin UUIDProperty;

    string name;       /// Source package name
    @Column ("version") string ver; /// Version of this package
    ArchiveSuite suite;         /// Suite this package is in
    ArchiveComponent component; /// Component this package is in

    string[] architectures; /// List of architectures this source package can be built for
    mixin (JsonDatabaseField!("architectures", "architectures", "string[]"));
    PackageInfo[] binaries;
    mixin (JsonDatabaseField!("binaries", "binaries", "PackageInfo[]"));

    @Null string standardsVersion;
    string format;

    @Null string homepage;
    @Null string vcsBrowser;

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

        string repo = "";
        if (this.suite !is null) {
            repo = this.suite.repo.name;
            if (repo.empty)
                repo = "master";
        }

        this.uuid = sha1UUID (repo ~ "::" ~ this.name);
    }
}

/**
 * Data of a binary package.
 */
@Table("archive_bin_package")
class BinaryPackage
{
    mixin UUIDProperty;

    DebType debType;   /// Deb package type
    mixin (EnumDatabaseField! ("deb_type", "debType", "DebType", true));

    string name;       /// Package name
    @Column ("version") string ver; /// Version of this package
    ArchiveSuite suite;         /// Suite this package is in
    ArchiveComponent component; /// Component this package is in

    ArchiveArchitecture architecture; /// Architecture this binary was built for
    int installedSize; /// Size of the installed package (an int instead of e.g. ulong for now for database reasons)

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

    @Null string homepage;

    void ensureUUID (bool regenerate = false)
    {
        import std.uuid : sha1UUID;
        import std.array : empty;
        if (this.uuid.empty && !regenerate)
            return;

        string repo = "";
        if (this.suite !is null) {
            repo = this.suite.repo.name;
            if (repo.empty)
                repo = "master";
        }

        this.uuid = sha1UUID (repo ~ "::" ~ this.name ~ "/" ~ this.ver);
    }
}


import laniakea.db.database : Database;


/**
 * Create initial tables for this module.
 */
void createTables (Database db) @trusted
{
    import laniakea.db.schema.archive;
    auto conn = db.getConnection ();
    scope (exit) db.dropConnection (conn);
    auto stmt = conn.createStatement();
    scope(exit) stmt.close();

    stmt.executeUpdate (
        "CREATE TABLE IF NOT EXISTS config (
          id text PRIMARY KEY,
          data jsonb NOT NULL
        )"
    );

    auto factory = db.newSessionFactory ();
    scope (exit) factory.close();

    // create tables if they don't exist yet
    factory.getDBMetaData ().updateDBSchema (conn, false, true);

    // ensure we use the right datatypes - the ORM is not smart enough to
    // figure out the proper types
    stmt.executeUpdate (
        "ALTER TABLE archive_component
         ALTER COLUMN dependencies TYPE JSONB USING dependencies::jsonb;"
    );

    stmt.executeUpdate (
        "ALTER TABLE archive_src_package
         ALTER COLUMN version       TYPE DEBVERSION,
         ALTER COLUMN standards_version TYPE DEBVERSION,
         ALTER COLUMN architectures TYPE JSONB USING architectures::jsonb,
         ALTER COLUMN binaries      TYPE JSONB USING binaries::jsonb,
         ALTER COLUMN uploaders     TYPE JSONB USING uploaders::jsonb,
         ALTER COLUMN buildDepends  TYPE JSONB USING buildDepends::jsonb,
         ALTER COLUMN files         TYPE JSONB USING files::jsonb;"
    );

    stmt.executeUpdate (
        "ALTER TABLE archive_bin_package
         ALTER COLUMN version    TYPE DEBVERSION,
         ALTER COLUMN depends    TYPE JSONB USING depends::jsonb,
         ALTER COLUMN preDepends TYPE JSONB USING preDepends::jsonb,
         ALTER COLUMN file       TYPE JSONB USING file::jsonb;"
    );
}

auto getSuite (Session session, string name, string repo = "master") @trusted
{
    auto q = session.createQuery ("FROM ArchiveSuite WHERE name=:nm")
                    .setParameter ("nm", name);
    ArchiveSuite[] list = q.list!ArchiveSuite();

    if (list.empty)
        return null;
    auto suite = list[0];
    return suite;
}

auto getSuites (Session session, string repo = "master") @trusted
{
    auto q = session.createQuery ("FROM ArchiveSuite suite WHERE suite.repo.name=:repo")
                    .setParameter ("repo", repo);
    return q.list!ArchiveSuite();
}

auto getPackageSuites (T) (Session session, string repoName, string component, string name) @trusted
{
    static assert (is(T == SourcePackage) || is(T == BinaryPackage));

    import std.algorithm : uniq, map;

    static if (is(T == SourcePackage))
        enum entityName = "SourcePackage";
    else
        enum entityName = "BinaryPackage";

    auto rows = session.createQuery("SELECT pkg.suite.name
                                     FROM " ~ entityName ~ " AS pkg
                                     WHERE pkg.suite.repo.name = :repoName
                                       AND pkg.component.name=:componentName
                                       AND pkg.name=:pkgName")
                       .setParameter("repoName", "master")
                       .setParameter("componentName", component)
                       .setParameter("pkgName", name).listRows ();

    return rows.map! (r => r[0].toString).uniq;
}
