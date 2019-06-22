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

module lknative.repository.types;
@safe:

import std.array : empty;
import std.uuid : UUID;

/**
 * A system architecture software can be compiled for.
 * Usually associated with an @ArchiveSuite
 */
class ArchiveRepository
{
    int id;

    string name; /// Name of the repository

    ArchiveSuite[] suites;

    BinaryPackage[] binPackages;
    BinaryPackage[] srcPackages;

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
    int id;

    string name;

    ArchiveRepository repo;

    ArchiveArchitecture[] architectures;

    ArchiveComponent[] components;

    ArchiveSuite baseSuite;

    BinaryPackage[] binPackages;
    BinaryPackage[] srcPackages;

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
    int id;

    string name;

    ArchiveSuite[] suites;

    string[] dependencies; /// Other components that need to be present to fulfill dependencies of packages in this component

    BinaryPackage[] binPackages;
    BinaryPackage[] srcPackages;

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
    int id;

    string name;

    ArchiveSuite[] suites; /// Suites that contain this architecture

    BinaryPackage[] binPackages;

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
struct SourcePackage
{
    UUID uuid;
    UUID sourceUUID;        /// The unique identifier for the whole source packaging project (stays the same even if the package version changes)

    string name; /// Source package name
    string ver;  /// Version of this package

    ArchiveSuite[] suites; /// Suites this package is in
    ArchiveComponent component;         /// Component this package is in
    ArchiveRepository repo;             /// Repository this package is part of

    string[] architectures; /// List of architectures this source package can be built for
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
struct BinaryPackage
{
    UUID uuid;
    DebType debType;   /// Deb package type

    string name;       /// Package name
    string ver; /// Version of this package

    ArchiveSuite[] suites; /// Suites this package is in
    ArchiveComponent component;         /// Component this package is in
    ArchiveRepository repo;             /// Repository this package is part of

    ArchiveArchitecture architecture; /// Architecture this binary was built for
    int installedSize; /// Size of the installed package (an int instead of e.g. ulong for now for database reasons)

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

static if (0) {

/**
 * Description of a software component as described by the AppStream
 * specification.
 */
class SoftwareComponent
{
    import appstream.Metadata : Metadata;
    UUID uuid;

    ASComponentKind kind; /// The component type

    string cid;        /// The component ID of this software
    string gcid; /// The global component ID as used by appstream-generator

    string name;              /// Name of this component
    string summary;           /// Short description of this component
    string description; /// Description of this component

    string iconName;       /// Name of the primary cached icon of this component

    string projectLicense; /// License of this software
    string developerName;  /// Name of the developer of this software

    string[] categories;      /// Categories this component is in

    BinaryPackage[] binPackages;

    ASComponent _cpt; /// The AppStream component this database entity represents

    string xml;  /// XML representation in AppStream collection XML for this component
    string yaml; /// YAML representation of the AppStream component data

    alias _cpt this;

    /**
     * Load the actual AppStream component from stored XML or YAML data,
     * using an existing AppStream metadata parser instance.
     */
    public void load (Metadata mdata) @trusted
    {
        import appstream.c.types : FormatStyle, FormatKind;

        mdata.clearComponents ();
        mdata.setFormatStyle (FormatStyle.COLLECTION);

        if (!xml.empty)
            mdata.parse (xml, FormatKind.XML);
        else if (!yaml.empty)
            mdata.parse (yaml, FormatKind.YAML);
        else
            throw new Exception("Can not load AppStream component from empty data.");

        _cpt = mdata.getComponent ();
        _cpt.setActiveLocale ("C");
    }

    /**
     * Load the actual AppStream component from stored XML or YAML data.
     */
    public void load () @trusted
    {
        auto mdata = new Metadata;
        load (mdata);
    }

    /**
     * Update the unique identifier for this component.
     */
    public void updateUUID ()
    {
        import std.uuid : sha1UUID;
        if (!gcid.empty)
            this.uuid = sha1UUID (gcid);
        else if (!xml.empty)
            this.uuid = sha1UUID (xml);
        else if (!yaml.empty)
            this.uuid = sha1UUID (yaml);
    }
}

}
