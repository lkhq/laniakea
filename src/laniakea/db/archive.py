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

import json
import enum
import uuid
from sqlalchemy import Column, Table, Index, Text, String, Integer, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import ARRAY, CHAR, JSON, TEXT
from sqlalchemy.sql import func, cast
from .base import Base, UUID, DebVersion, create_tsvector


UUID_NS_SRCPACKAGE = uuid.UUID('bdc4cc28-43ed-58f7-8cf8-7bd1b4e80560')
UUID_NS_BINPACKAGE = uuid.UUID('b897829c-2eb4-503c-afd1-0fd74da8cc2b')
UUID_NS_SWCOMPONENT = uuid.UUID('94c8e196-e236-48fe-81c8-38dd47de4650')


repo_suite_assoc_table = Table('archive_repo_suite_association', Base.metadata,
                               Column('repo_id', Integer, ForeignKey('archive_repositories.id')),
                               Column('suite_id', Integer, ForeignKey('archive_suites.id'))
                               )


class ArchiveRepository(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_repositories'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    suites = relationship('ArchiveSuite', secondary=repo_suite_assoc_table, back_populates='repos')

    def __init__(self, name):
        self.name = name


suite_component_assoc_table = Table('archive_suite_component_association', Base.metadata,
                                    Column('suite_id', Integer, ForeignKey('archive_suites.id')),
                                    Column('component_id', Integer, ForeignKey('archive_components.id'))
                                    )

suite_arch_assoc_table = Table('archive_suite_architecture_association', Base.metadata,
                               Column('suite_id', Integer, ForeignKey('archive_suites.id')),
                               Column('arch_id', Integer, ForeignKey('archive_architectures.id'))
                               )

srcpkg_suite_assoc_table = Table('archive_srcpkg_suite_association', Base.metadata,
                                 Column('src_package_uuid', UUID(as_uuid=True), ForeignKey('archive_src_packages.uuid')),
                                 Column('suite_id', Integer, ForeignKey('archive_suites.id'))
                                 )

binpkg_suite_assoc_table = Table('archive_binpkg_suite_association', Base.metadata,
                                 Column('bin_package_uuid', UUID(as_uuid=True), ForeignKey('archive_bin_packages.uuid')),
                                 Column('suite_id', Integer, ForeignKey('archive_suites.id'))
                                 )

swcpt_binpkg_assoc_table = Table('archive_swcpt_binpkg_association', Base.metadata,
                                 Column('sw_cpt_uuid', UUID(as_uuid=True), ForeignKey('archive_sw_components.uuid')),
                                 Column('bin_package_uuid', UUID(as_uuid=True), ForeignKey('archive_bin_packages.uuid'))
                                 )


class ArchiveSuite(Base):
    '''
    Information about suite in a distribution repository.
    '''
    __tablename__ = 'archive_suites'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository

    accept_uploads = Column(Boolean(), default=True)  # Whether new packages can arrive in this suite via regular uploads ("unstable", "staging", ...)
    devel_target = Column(Boolean(), default=False)  # Whether this is a development target suite ("testing", "green", ...)
    frozen = Column(Boolean(), default=False)  # Whether the suite is fozen and immutable for changes

    repos = relationship('ArchiveRepository', secondary=repo_suite_assoc_table, back_populates='suites')
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
            if arch.name != 'all':
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

    def __init__(self, name):
        self.name = name

    def is_primary(self):
        return self.name == 'main'

    def is_nonfree(self):
        return self.name == 'non-free'


class ArchiveArchitecture(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_architectures'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    summary = Column(String(256))  # Short description of this architecture

    suites = relationship('ArchiveSuite', secondary=suite_arch_assoc_table, back_populates='architectures')  # Suites that contain this architecture

    bin_packages = relationship('BinaryPackage', backref=backref('ArchiveArchitecture', uselist=False))

    def __init__(self, name):
        self.name = name


class PackageType(enum.IntEnum):
    '''
    Type of the package.
    '''
    UNKNOWN = 0
    SOURCE = enum.auto()
    BINARY = enum.auto()


class DebType(enum.IntEnum):
    '''
    Type of the Debian package.
    '''
    UNKNOWN = 0
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


class PackagePriority(enum.IntEnum):
    '''
    Priority of a Debian package.
    '''
    UNKNOWN = 0
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


class VersionPriority(enum.IntEnum):
    '''
    Priority of a package upload.
    '''
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3
    EMERGENCY = 4

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


class PackageInfo:
    '''
    Basic package information, used by
    :SourcePackage to refer to binary packages.
    '''
    deb_type = DebType.DEB
    name = None
    version = None


class ArchiveFile(Base):
    '''
    A file in the archive.
    '''
    __tablename__ = 'archive_files'

    id = Column(Integer, primary_key=True)

    fname = Column(Text())
    size = Column(Integer())  # the size of the file
    sha256sum = Column(CHAR(64))  # the files' checksum

    srcpkg_id = Column(UUID(as_uuid=True), ForeignKey('archive_src_packages.uuid'))
    binpkg_id = Column(UUID(as_uuid=True), ForeignKey('archive_bin_packages.uuid'), unique=True, nullable=True)
    binpkg = relationship('BinaryPackage', back_populates='pkg_file')
    srcpkg = relationship('SourcePackage', back_populates='files')

    def make_url(self, urlbase):
        if urlbase[-1] == '/':
            return urlbase + str(self.fname)
        else:
            return urlbase + '/' + str(self.fname)


class SourcePackage(Base):
    '''
    Data of a source package.
    '''
    __tablename__ = 'archive_src_packages'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)
    source_uuid = Column(UUID(as_uuid=True), default=None, nullable=False)  # The unique identifier for the whole source packaging project (stays the same even if the package version changes)

    name = Column(String(256))  # Source package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    suites = relationship('ArchiveSuite', secondary=srcpkg_suite_assoc_table, back_populates='src_packages')  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this package is in

    architectures = Column(ARRAY(String(64)))  # List of architectures this source package can be built for

    _binaries_json = Column('binaries', JSON)

    standards_version = Column(String(256))
    format_version = Column(String(64))

    homepage = Column(Text())
    vcs_browser = Column(Text())

    maintainer = Column(Text())
    uploaders = Column(ARRAY(Text()))

    build_depends = Column(ARRAY(Text()))

    files = relationship('ArchiveFile', back_populates='srcpkg')
    directory = Column(Text())

    @property
    def binaries(self):
        data = json.loads(self._binaries_json)
        res = []
        for e in data:
            info = PackageInfo()
            info.deb_type = e.get('deb_type', DebType.DEB)
            info.name = e.get('name')
            info.version = e.get('version')
            res.append(info)
        return info

    @binaries.setter
    def binaries(self, value):
        if not type(value) is list:
            value = [value]

        data = []
        for v in value:
            d = {'deb_type': v.deb_type,
                 'name': v.name,
                 'version': v.version}
            data.append(d)
        self._binaries_json = json.dumps(data)

    def update_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.update_source_uuid()
        self.uuid = uuid.uuid5(UUID_NS_SRCPACKAGE, '{}::source/{}/{}'.format(self.repo.name, self.name, self.version))

        return self.uuid

    def update_source_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.source_uuid = uuid.uuid5(UUID_NS_SRCPACKAGE, '{}::source/{}'.format(self.repo.name, self.name))
        return self.source_uuid

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        return '{}::source/{}/{}'.format(repo_name, self.name, self.version)


def auto_binpkg_uuid(context):
    return context.get_current_parameters()['counter'] + 12


class BinaryPackage(Base):
    '''
    Data of a binary package.
    '''
    __tablename__ = 'archive_bin_packages'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)
    deb_type = Column(Enum(DebType))  # Deb package type

    name = Column(String(256))  # Package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    suites = relationship('ArchiveSuite', secondary=binpkg_suite_assoc_table, back_populates='bin_packages')  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this package is in

    architecture_id = Column(Integer, ForeignKey('archive_architectures.id'))
    architecture = relationship('ArchiveArchitecture')  # Architecture this binary was built for

    size_installed = Column(Integer())  # Size of the installed package

    description = Column(Text())
    description_md5 = Column(CHAR(32))

    source_name = Column(String(256))
    source_version = Column(DebVersion())

    priority = Column(Enum(PackagePriority))

    section = Column(String(64))

    depends = Column(ARRAY(Text()))
    pre_depends = Column(ARRAY(Text()))

    maintainer = Column(Text())
    homepage = Column(Text())

    pkg_file = relationship('ArchiveFile', uselist=False, back_populates='binpkg')
    sw_cpts = relationship('SoftwareComponent', secondary=swcpt_binpkg_assoc_table, back_populates='bin_packages')

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT),
        cast(func.coalesce(source_name, ''), TEXT)
    )

    __table_args__ = (
        Index(
            'idx_bin_package_fts',
            __ts_vector__,
            postgresql_using='gin'
        ),
    )

    def update_uuid(self):
        if not self.repo:
            raise Exception('Binary package is not associated with a repository!')

        self.uuid = uuid.uuid5(UUID_NS_BINPACKAGE, '{}::{}/{}/{}'.format(self.repo.name, self.name, self.version, self.architecture.name))
        return self.uuid

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        arch_name = 'unknown'
        if self.architecture:
            arch_name = self.architecture.name
        return '{}::{}/{}/{}'.format(repo_name, self.name, self.version, arch_name)


# index to speed up data imports, where packages belonging to a certain repository/arch combination
# are requested frequently
bin_package_repo_arch_index = Index('idx_bin_package_repo_arch',
                                    BinaryPackage.repo_id,
                                    BinaryPackage.architecture_id)


class SoftwareComponent(Base):
    '''
    Description of a software component as described by the AppStream
    specification.
    '''
    __tablename__ = 'archive_sw_components'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kind = Column(Integer())  # The component type

    cid = Column(Text())  # The component ID of this software
    gcid = Column(Text())  # The global component ID as used by appstream-generator

    name = Column(Text())  # Name of this component
    summary = Column(Text())  # Short description of this component
    description = Column(Text())  # Description of this component

    icon_name = Column(String(256))  # Name of the primary cached icon of this component

    project_license = Column(Text())  # License of this software
    developer_name = Column(Text())  # Name of the developer of this software

    categories = Column(ARRAY(String(256)))  # Categories this component is in

    bin_packages = relationship('BinaryPackage', secondary=swcpt_binpkg_assoc_table, back_populates='sw_cpts')  # Packages this software component is contained in

    xml = Column(Text())  # XML representation in AppStream collection XML for this component

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(summary, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT)
    )

    __table_args__ = (
        Index(
            'idx_sw_components_fts',
            __ts_vector__,
            postgresql_using='gin'
        ),
    )

    cpt = None

    def update_uuid(self):
        '''
        Update the unique identifier for this component.
        '''
        if not self.gcid and not self.xml:
            raise Exception('Global component ID is not set for this component, and no XML data was found for it. Can not create UUID.')

        self.uuid = uuid.uuid5(UUID_NS_SWCOMPONENT, self.gcid if self.gcid else self.xml)
        return self.uuid

    def load(self, mdata=None):
        '''
        Load the actual AppStream component from stored XML data.
        An existing Metadata instance can be reused.
        '''
        if not mdata:
            import gi
            gi.require_version('AppStream', '1.0')
            from gi.repository import AppStream
            mdata = AppStream.Metadata()

        mdata.clear_components()
        mdata.set_format_style(AppStream.FormatStyle.COLLECTION)

        if not self.xml:
            raise Exception('Can not load AppStream component from empty data.')

        mdata.parse(self.xml, AppStream.FormatKind.XML)
        self.cpt = mdata.get_component()
        self.cpt.set_active_locale('C')

        return self.cpt


def get_archive_sections():
    '''
    Retrieve a list of dictionaries describing the archive
    sections that are currently supported.
    This function does read a local data file, instead of information
    from the database.
    '''
    import json
    from laniakea.localconfig import get_data_file

    with open(get_data_file('archive-sections.json'), 'r') as f:
        sections = json.load(f)

    # validate & refine data
    for section in sections:
        if 'name' not in section:
            raise Exception('Invalid section contained in archive sections file (name missing).')
        if 'summary' not in section:
            section['summary'] = 'The {} section'.format(section['name'])

    return sections
