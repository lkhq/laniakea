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

    LazyCollection!BinaryPackage binPackages;
    LazyCollection!BinaryPackage srcPackages;

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

    @ManyToMany
    LazyCollection!BinaryPackage binPackages;
    @ManyToMany
    LazyCollection!BinaryPackage srcPackages;

    this () {}
    this (string name)
    {
        this.name = name;
    }

    private ArchiveArchitecture _primaryArch;
    auto primaryArchitecture () @trusted
    {
        if (_primaryArch !is null)
            return _primaryArch;
        if (architectures.length == 0)
            return null;
        _primaryArch = architectures[0];
        foreach (ref arch; architectures) {
            if (arch.name != "all") {
                _primaryArch = arch;
                break;
            }
        }
        return _primaryArch;
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

    UUID sourceUUID;        /// The unique identifier for the whole source packaging project (stays the same even if the package version changes)
    @property @Column ("source_uuid") string sourceUUID_s () { return sourceUUID.toString; }
    @property @Column ("source_uuid") void sourceUUID_s (string s) { sourceUUID = UUID (s); }

    string name;       /// Source package name
    @Column ("version") string ver; /// Version of this package

    @ManyToMany
    LazyCollection!ArchiveSuite suites; /// Suites this package is in
    ArchiveComponent component;         /// Component this package is in
    ArchiveRepository repo;             /// Repository this package is part of

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
    mixin (JsonDatabaseField!("build_depends", "buildDepends", "string[]"));

    ArchiveFile[] files;
    mixin (JsonDatabaseField!("files", "files", "ArchiveFile[]"));
    string directory;

    static auto generateUUID (const string repoName, const string pkgname, const string ver)
    {
        import std.uuid : sha1UUID;
        return sha1UUID (repoName ~ "::source/" ~ pkgname ~ "/" ~ ver);
    }

    void ensureUUID (bool regenerate = false) @trusted
    {
        import std.uuid : sha1UUID;
        import std.array : empty;
        if (this.uuid.empty && this.sourceUUID.empty && !regenerate)
            return;

        string repoName = "?";
        if (this.repo !is null) {
            repoName = this.repo.name;
        }

        this.uuid = SourcePackage.generateUUID (repoName, this.name, this.ver);
        this.sourceUUID = sha1UUID (repoName ~ "::" ~ this.name);
    }

    string stringId () @trusted
    {
        string repoName = "";
        if (this.suites.length != 0) {
            repoName = this.suites[0].repo.name;
            if (repoName.empty)
                repoName = "?";
        }

        return repoName ~ "::source/" ~ this.name ~ "/" ~ this.ver;
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

    @ManyToMany
    LazyCollection!ArchiveSuite suites; /// Suites this package is in
    ArchiveComponent component;         /// Component this package is in
    ArchiveRepository repo;             /// Repository this package is part of

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
    mixin (JsonDatabaseField! ("pre_depends", "preDepends", "string[]"));

    string maintainer;

    ArchiveFile file;
    mixin (JsonDatabaseField! ("file", "file", "ArchiveFile"));

    @Null string homepage;

    static auto generateUUID (const string repoName, const string pkgname, const string ver, const string arch)
    {
        import std.uuid : sha1UUID;
        return sha1UUID (repoName ~ "::" ~ pkgname ~ "/" ~ ver ~ "/" ~ arch);
    }

    void ensureUUID (bool regenerate = false) @trusted
    {
        import std.array : empty;
        if (this.uuid.empty && !regenerate)
            return;
        assert (this.architecture !is null);

        string repoName = "?";
        if (this.repo !is null) {
            repoName = this.repo.name;
        }

        this.uuid = BinaryPackage.generateUUID (repoName, this.name, this.ver, this.architecture.name);
    }

    string stringId () @trusted
    {
        assert (this.architecture !is null);

        string repoName = "";
        if (this.suites.length != 0) {
            repoName = this.suites[0].repo.name;
            if (repoName.empty)
                repoName = "?";
        }

        return repoName ~ "::" ~ this.name ~ "/" ~ this.ver ~ "/" ~ this.architecture.name;
    }
}


import laniakea.db.database : Database;
import laniakea.db.schema.jobs : Job;


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
         ALTER COLUMN build_depends TYPE JSONB USING build_depends::jsonb,
         ALTER COLUMN files         TYPE JSONB USING files::jsonb;"
    );

    stmt.executeUpdate (
        "ALTER TABLE archive_bin_package
         ALTER COLUMN version     TYPE DEBVERSION,
         ALTER COLUMN depends     TYPE JSONB USING depends::jsonb,
         ALTER COLUMN pre_depends TYPE JSONB USING pre_depends::jsonb,
         ALTER COLUMN file        TYPE JSONB USING file::jsonb;"
    );

    // Indices for SourcePackage
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_src_package_source_uuid_idx
                         ON archive_src_package (source_uuid)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_src_package_name_version_idx
                         ON archive_src_package (name, version)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_src_package_ftsearch
                         ON archive_src_package USING GIN(to_tsvector('english', name));");

    // Indices for BinaryPackage
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_bin_package_name_version_idx
                         ON archive_bin_package (name, version)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_bin_package_source_name_version_idx
                         ON archive_bin_package (source_name, source_version)");
    stmt.executeUpdate ("CREATE INDEX IF NOT EXISTS archive_bin_package_ftsearch
                         ON archive_bin_package USING GIN(to_tsvector('english', name || ' ' || description));");
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

auto getPackageSuites (T) (Connection conn, string repoName, string name) @trusted
{
    import std.array : appender, array;
    import std.algorithm : sort;
    import containers : OpenHashSet;
    static assert (is(T == SourcePackage) || is(T == BinaryPackage));

    static if (is(T == SourcePackage)) {
        enum entityTabName = "archive_src_package";
        enum suiteJoinSQL = "LEFT JOIN archive_suite_source_packages AS _t3 ON _t3.source_package_fk=_t1.uuid";
    } else {
        enum entityTabName = "archive_bin_package";
        enum suiteJoinSQL = "LEFT JOIN archive_suite_binary_packages AS _t3 ON _t3.binary_package_fk=_t1.uuid";
    }

    // we need to use raw SQL here because Hibernated doesn't implement all HQL features for such a query and generates garbage
    auto ps = conn.prepareStatement ("SELECT _t4.* FROM " ~ entityTabName ~ " AS _t1
                                        LEFT JOIN archive_repository AS _t2 ON _t1.archive_repository_fk=_t2.id
                                        " ~ suiteJoinSQL ~ "
                                        LEFT JOIN archive_suite as _t4 ON _t3.archive_suite_fk=_t4.id
                                      WHERE _t2.name = ? AND _t1.name = ?");

    scope (exit) ps.close ();
    ps.setString (1, repoName);
    ps.setString (2, name);

    auto rs = ps.executeQuery ();
    rs.first ();

    OpenHashSet!string suiteNames;
    if (rs.getFetchSize > 0) {
        do {
            suiteNames.insert (rs.getString (2));
        } while (rs.next ());
    }

    return array (suiteNames[]).sort;
}

/**
 * Get the source package that is associated with the selected job.
 */
auto getSourcePackageForJob (Session session, const ref Job packageJob) @trusted
{
    auto q = session.createQuery ("FROM SourcePackage WHERE sourceUUID_s=:trigger
                                   AND ver=:version")
                    .setParameter ("trigger", packageJob.trigger.toString)
                    .setParameter ("version", packageJob.ver);
    auto list = q.list!SourcePackage;
    if (list.empty)
        return null;
    return list[0];
}
