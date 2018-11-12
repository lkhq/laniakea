# Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import enum
from typing import List
from sqlalchemy import Column, Table, Text, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy import text as sa_text
from uuid import uuid4
from .base import Base, UUID, DebVersion
from .core import LkModule


class ArchiveRepository(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_repositories'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository

    suites = relationship('ArchiveSuite', backref='repo')


suite_component_assoc_table = Table('archive_suite_component_association', Base.metadata,
    Column('suite_id', Integer, ForeignKey('archive_suites.id')),
    Column('component_id', Integer, ForeignKey('archive_components.id'))
)

suite_arch_assoc_table = Table('archive_suite_architecture_association', Base.metadata,
    Column('suite_id', Integer, ForeignKey('archive_suites.id')),
    Column('arch_id', Integer, ForeignKey('archive_architectures.id'))
)

srcpkg_suite_assoc_table = Table('archive_srcpkg_suite_association', Base.metadata,
    Column('src_package_uuid', UUID, ForeignKey('archive_src_packages.uuid')),
    Column('suite_id', Integer, ForeignKey('archive_suites.id'))
)

binpkg_suite_assoc_table = Table('archive_binpkg_suite_association', Base.metadata,
    Column('bin_package_uuid', UUID, ForeignKey('archive_bin_packages.uuid')),
    Column('suite_id', Integer, ForeignKey('archive_suites.id'))
)

class ArchiveSuite(Base):
    '''
    Information about suite in a distribution repository.
    '''
    __tablename__ = 'archive_suites'

    id = Column(Integer, primary_key=True)

    name = Column(String(128))  # Name of the repository

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))

    architectures = relationship('ArchiveArchitecture', secondary=suite_arch_assoc_table, back_populates='suites')
    components = relationship('ArchiveComponent', secondary=suite_component_assoc_table, back_populates='suites')

    parent_id = Column(Integer, ForeignKey('archive_suites.id'))
    parent = relationship('ArchiveSuite', remote_side=[id])

    src_packages = relationship('SourcePackage', secondary=srcpkg_suite_assoc_table, back_populates='suites')
    bin_packages = relationship('BinaryPackage', secondary=binpkg_suite_assoc_table, back_populates='suites')

    _primary_arch = None

    @property
    def primary_architecture(self):
        if self._primary_arch:
            return self._primary_arch
        if len(self.architectures) == 0:
            return None
        self._primary_arch = self.architectures[0]
        for arch in self.architectures:
            if arch.name is not 'all':
                self._primary_arch = arch
                break
        return self._primary_arch


class ArchiveComponent(Base):
    '''
    Information about an archive component within a suite.
    '''
    __tablename__ = 'archive_components'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository

    suites = relationship('ArchiveSuite', secondary=suite_component_assoc_table, back_populates='components')

    parent_component_id = Column(Integer, ForeignKey('archive_components.id'))
    parent_component = relationship('ArchiveComponent', remote_side=[id])  # Other components that need to be present to fulfill dependencies of packages in this component


class ArchiveArchitecture(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_architectures'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository

    suites = relationship('ArchiveSuite', secondary=suite_arch_assoc_table, back_populates='architectures')  # Suites that contain this architecture

    bin_packages = relationship('BinaryPackage', backref=backref('ArchiveArchitecture', uselist=False))


class PackageType(enum.Enum):
    '''
    Type of the package.
    '''
    UNKNOWN = enum.auto()
    SOURCE = enum.auto()
    BINARY = enum.auto()


class DebType(enum.Enum):
    '''
    Type of the Debian package.
    '''
    UNKNOWN = enum.auto()
    DEB = enum.auto()
    UDEB = enum.auto()

    def __str__(self):
        if self.value == DebType.DEB:
            return 'deb'
        elif self.value == DebType.UDEB:
            return 'udeb'
        return 'unknown'


def debtype_from_string(s):
    '''
    Convert the text representation into the enumerated type.
    '''
    if s == 'deb':
        return DebType.DEB
    elif s == 'udeb':
        return DebType.UDEB
    return DebType.UNKNOWN


class PackagePriority(enum.Enum):
    '''
    Priority of a Debian package.
    '''
    UNKNOWN = enum.auto()
    REQUIRED = enum.auto()
    IMPORTANT = enum.auto()
    STANDARD = enum.auto()
    OPTIONAL = enum.auto()
    EXTRA = enum.auto()


def packagepriority_from_string(s):
    '''
    Convert the text representation into the enumerated type.
    '''
    if s == 'optional':
        return PackagePriority.OPTIONAL
    elif s == 'extra':
        return PackagePriority.EXTRA
    elif s == 'standard':
        return PackagePriority.STANDARD
    elif s == 'important':
        return PackagePriority.IMPORTANT
    elif s == 'required':
        return PackagePriority.REQUIRED
    return PackagePriority.UNKNOWN


class VersionPriority(enum.Enum):
    '''
    Priority of a package upload.
    '''
    LOW = enum.auto()
    MEDIUM = enum.auto()
    HIGH = enum.auto()
    CRITICAL = enum.auto()
    EMERGENCY = enum.auto()

    def __str__(self):
        if self.value == VersionPriority.LOW:
            return 'low'
        elif self.value == VersionPriority.MEDIUM:
            return 'medium'
        elif self.value == VersionPriority.HIGH:
            return 'high'
        elif self.value == VersionPriority.CRITICAL:
            return 'critical'
        elif self.value == VersionPriority.EMERGENCY:
            return 'emergency'
        return 'unknown'


class ArchiveFile:
    '''
    A file in the archive.
    '''

    fname = None  # the filename of the file
    size = 0  # the size of the file
    sha256sum = None  # the files' checksum


class PackageInfo:
    '''
    Basic package information, used by
    :SourcePackage to refer to binary packages.
    '''
    deb_type = DebType.DEB
    name = None
    version = None

    section = None
    priority = PackagePriority.OPTIONAL
    architectures = []


class SourcePackage(Base):
    '''
    Data of a source package.
    '''
    __tablename__ = 'archive_src_packages'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_uuid = Column(UUID(as_uuid=True), default=uuid4)  # The unique identifier for the whole source packaging project (stays the same even if the package version changes)

    name = Column(String(256))  # Source package name
    version = Column(DebVersion())  # Version of this package

    suites = relationship('ArchiveSuite', secondary=srcpkg_suite_assoc_table, back_populates='src_packages')  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))  # Component this package is in

    architectures = Column(ARRAY(String(64)))  # List of architectures this source package can be built for

    #PackageInfo[] binaries;

    standards_version = Column(String(256))
    pkgformat = Column(String(64))

    homepage = Column(Text())
    vcs_browser = Column(Text())

    maintainer = Column(Text())
    uploaders = Column(ARRAY(Text()))

    build_depends = Column(ARRAY(Text()))

    #ArchiveFile[] files;
    directory = Column(Text())


"""
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

"""


class BinaryPackage(Base):
    '''
    Data of a binary package.
    '''
    __tablename__ = 'archive_bin_packages'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    deb_type = Column(Enum(DebType)) # Deb package type

    name = Column(String(256))  # Package name
    version = Column(DebVersion())  # Version of this package

    suites = relationship('ArchiveSuite', secondary=binpkg_suite_assoc_table, back_populates='bin_packages')  # Suites this package is in
    component_id = Column(Integer, ForeignKey('archive_components.id'))  # Component this package is in

    architecture_id = Column(Integer, ForeignKey('archive_architectures.id'))  # Architecture this binary was built for

"""
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

"""
