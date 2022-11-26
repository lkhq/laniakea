# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import enum
import json
import uuid
import typing as T
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy import (
    Enum,
    Text,
    Index,
    Table,
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    BigInteger,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import cast, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import CHAR, JSON, TEXT, ARRAY, JSONB

from .base import UUID, Base, DebVersion, create_tsvector

UUID_NS_SRCPACKAGE = uuid.UUID('bdc4cc28-43ed-58f7-8cf8-7bd1b4e80560')
UUID_NS_BINPACKAGE = uuid.UUID('b897829c-2eb4-503c-afd1-0fd74da8cc2b')
UUID_NS_SWCOMPONENT = uuid.UUID('94c8e196-e236-48fe-81c8-38dd47de4650')


uploader_repo_assoc_table = Table(
    'archive_uploader_repo_association',
    Base.metadata,
    Column('uploader_id', Integer, ForeignKey('archive_uploaders.id', ondelete='cascade')),
    Column('repo_id', Integer, ForeignKey('archive_repositories.id')),
)


class ArchiveError(Exception):
    """Some issue occurred with the package archive."""


class ArchiveConfig(Base):
    """
    General archive configuration that applies to all repositories and suites.
    """

    __tablename__ = 'archive_config'

    id = Column(Integer, primary_key=True)

    primary_repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    primary_repo = relationship('ArchiveRepository')
    # If True, Laniakea will automatically create, delete and assign debug suites
    auto_debug_management = Column(Boolean(), default=True)

    # Location (directory) of the primary/master repository
    primary_repo_root = Column(Text(), nullable=False, default='/')
    extra_repo_root = Column(Text(), nullable=False, default='/multiverse')  # Location of the additional repositories

    archive_url = Column(Text(), nullable=False)  # Web URL of the primary archive mirror


class ArchiveRepository(Base):
    """
    A repository of packages.
    """

    __tablename__ = 'archive_repositories'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    origin_name = Column(String(200))  # Name of the origin of this repository (e.g. "Purism")
    is_debug = Column(Boolean(), default=False)  # If True, this repository is used for debug suites

    debug_repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    # Indicates the debug-symbol repository that belongs to this repository (if any)
    debug_repo_for = relationship('ArchiveRepository', backref=backref('debug_repo', remote_side=[id]))

    uploaders = relationship('ArchiveUploader', secondary=uploader_repo_assoc_table, back_populates='repos')

    suite_settings = relationship('ArchiveRepoSuiteSettings', back_populates='repo', uselist=True)

    # map upload suites to the actual suite automatically
    upload_suite_map = Column(MutableDict.as_mutable(JSON), default={})

    def __init__(self, name):
        self.name = name

    def get_root_dir(self) -> str:
        """Get the absolute path to the repository's root directory"""
        from laniakea import LocalConfig

        return os.path.join(LocalConfig().archive_root_dir, self.name)

    def get_new_queue_dir(self) -> str:
        """Get the absolute path to the repository's NEW queue directory"""
        from laniakea import LocalConfig

        return os.path.join(LocalConfig().archive_queue_dir, self.name, 'new')

    def get_new_queue_url(self) -> str:
        """Get the web URL to the repository's NEW queue"""
        from laniakea import LocalConfig

        return os.path.join(LocalConfig().archive_queue_url, self.name, 'new')


suite_component_assoc_table = Table(
    'archive_suite_component_association',
    Base.metadata,
    Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
    Column('component_id', Integer, ForeignKey('archive_components.id', ondelete='cascade'), primary_key=True),
)

suite_arch_assoc_table = Table(
    'archive_suite_architecture_association',
    Base.metadata,
    Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
    Column('arch_id', Integer, ForeignKey('archive_architectures.id', ondelete='cascade'), primary_key=True),
)

suite_parents_assoc_table = Table(
    'archive_suite_parents_association',
    Base.metadata,
    Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
    Column('parent_suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
)

srcpkg_suite_assoc_table = Table(
    'archive_srcpkg_suite_association',
    Base.metadata,
    Column(
        'src_package_uuid',
        UUID(as_uuid=True),
        ForeignKey('archive_pkgs_source.uuid'),
        primary_key=True,
    ),
    Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
)

binpkg_suite_assoc_table = Table(
    'archive_binpkg_suite_association',
    Base.metadata,
    Column(
        'bin_package_uuid',
        UUID(as_uuid=True),
        ForeignKey('archive_pkgs_binary.uuid'),
        primary_key=True,
    ),
    Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'), primary_key=True),
)

srcpkg_file_assoc_table = Table(
    'archive_srcpkg_file_association',
    Base.metadata,
    Column(
        'src_package_uuid',
        UUID(as_uuid=True),
        ForeignKey('archive_pkgs_source.uuid', ondelete='cascade'),
        primary_key=True,
    ),
    Column('file_id', Integer, ForeignKey('archive_files.id'), primary_key=True),
)

swcpt_binpkg_assoc_table = Table(
    'archive_swcpt_binpkg_association',
    Base.metadata,
    Column(
        'sw_cpt_uuid',
        UUID(as_uuid=True),
        ForeignKey('archive_sw_components.uuid', ondelete='cascade'),
        primary_key=True,
    ),
    Column(
        'bin_package_uuid',
        UUID(as_uuid=True),
        ForeignKey('archive_pkgs_binary.uuid', ondelete='cascade'),
        primary_key=True,
    ),
)


class ArchiveUploader(Base):
    """
    Entities who are permitted to upload data to archive repositories.
    """

    __tablename__ = 'archive_uploaders'

    id = Column(Integer, primary_key=True)

    email = Column(Text(), unique=True)  # E-Mail address of this entity used for signing
    pgp_fingerprints = Column(ARRAY(Text()))  # Fingerprints of the GnuPG keys associated with this entity
    is_human = Column(Boolean(), default=True)  # Whether this entry applies to a human person or a machine

    name = Column(Text(), nullable=True)  # Full name of this uploader
    alias = Column(Text(), nullable=True)  # Alias or nickname of this uploader

    allow_source_uploads = Column(Boolean(), default=True)  # Whether source uploads are permitted
    allow_binary_uploads = Column(Boolean(), default=True)  # Whether binary package uploads are permitted
    # Whether uploads of this entity should always end up in the NEW queue
    always_review = Column(Boolean(), default=False)
    # Names of source packages that this entity is allowed to touch, empty to allow all
    allowed_packages = Column(ARRAY(Text()))

    repos = relationship('ArchiveRepository', secondary=uploader_repo_assoc_table, back_populates='uploaders')

    def __init__(self, email: str):
        self.email = email


class DbgSymPolicy(enum.Enum):
    """
    Policy for debug symbol handling for suites.
    """

    INVALID = 0
    NO_DEBUG = enum.auto()  # no debug symbols must be present in this suite (they may be moved to a separate suite)
    ONLY_DEBUG = enum.auto()  # this suite may only contain debug symbol packages
    DEBUG_ALLOWED = enum.auto()  # this suite may contain both regular and debug symbol packages

    def to_string(self):
        if self.value == self.NO_DEBUG.value:
            return 'no-debug'
        elif self.value == self.ONLY_DEBUG.value:
            return 'only-debug'
        elif self.value == self.DEBUG_ALLOWED.value:
            return 'debug-allowed'
        return 'invalid'

    def __str__(self):
        return self.to_string()

    @staticmethod
    def from_string(s: str) -> 'DbgSymPolicy':
        """
        Convert the text representation into the enumerated type.
        """
        if s == 'no-debug':
            return DbgSymPolicy.NO_DEBUG
        elif s == 'only-debug':
            return DbgSymPolicy.ONLY_DEBUG
        elif s == 'debug-allowed':
            return DbgSymPolicy.DEBUG_ALLOWED
        return DbgSymPolicy.INVALID


class NewPolicy(enum.Enum):
    """
    Policy for how new packages are processed.
    """

    INVALID = 0
    DEFAULT = enum.auto()  # default policy: only new source packages end up in the NEW queue
    ALWAYS_NEW = enum.auto()  # every single human upload ends up in the NEW queue for review
    NEVER_NEW = enum.auto()  # no package will end up in NEW, everything will be auto-accepted.

    def to_string(self):
        if self.value == self.DEFAULT.value:
            return 'default'
        elif self.value == self.ALWAYS_NEW.value:
            return 'always-new'
        elif self.value == self.NEVER_NEW.value:
            return 'never-new'
        return 'invalid'

    def __str__(self):
        return self.to_string()

    @staticmethod
    def from_string(s: str) -> 'NewPolicy':
        """
        Convert the text representation into the enumerated type.
        """
        if s == 'default':
            return NewPolicy.DEFAULT
        elif s == 'always-new':
            return NewPolicy.ALWAYS_NEW
        elif s == 'never-new':
            return NewPolicy.NEVER_NEW
        return NewPolicy.INVALID


class ArchiveSuite(Base):
    """
    Information about suite in a distribution repository.
    """

    __tablename__ = 'archive_suites'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the suite, usually the codename e.g. "sid"
    alias = Column(String(128), unique=True, nullable=True)  # Alternative name of the suite, e.g. "unstable"
    summary = Column(String(200), nullable=True)  # Short description string for this suite
    version = Column(String(64), nullable=True)  # Version string applicable for this suite
    dbgsym_policy = Column(
        Enum(DbgSymPolicy), default=DbgSymPolicy.NO_DEBUG
    )  # Set how debug symbol packages should be handled for this suite

    architectures = relationship('ArchiveArchitecture', secondary=suite_arch_assoc_table, back_populates='suites')
    components = relationship('ArchiveComponent', secondary=suite_component_assoc_table, back_populates='suites')

    debug_suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    debug_suite_for = relationship('ArchiveSuite', backref=backref('debug_suite', remote_side=[id]))

    repo_settings = relationship('ArchiveRepoSuiteSettings', back_populates='suite')

    parents = relationship(
        'ArchiveSuite',
        secondary=suite_parents_assoc_table,
        primaryjoin=id == suite_parents_assoc_table.c.suite_id,
        secondaryjoin=id == suite_parents_assoc_table.c.parent_suite_id,
        backref='overlays',
    )

    pkgs_source = relationship('SourcePackage', secondary=srcpkg_suite_assoc_table, back_populates='suites')
    pkgs_binary = relationship('BinaryPackage', secondary=binpkg_suite_assoc_table, back_populates='suites')

    _primary_arch = None

    def __init__(self, name: str, alias: str = None):
        self.name = name
        self.alias = alias

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


class ArchiveRepoSuiteSettings(Base):
    """
    Settings that are specific to a suite in a particular repository, but
    will not apply to the suite globally.
    """

    __tablename__ = 'archive_repo_suite_settings'
    __table_args__ = (UniqueConstraint('repo_id', 'suite_id', name='_repo_suite_uc'),)

    id = Column(Integer, primary_key=True)

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo: ArchiveRepository = relationship('ArchiveRepository', back_populates='suite_settings')

    suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    suite: ArchiveSuite = relationship('ArchiveSuite', back_populates='repo_settings')

    # Override the default suite summary text for the particular repository
    suite_summary = Column(String(200), nullable=True)
    # Whether new packages can arrive in this suite via regular uploads ("unstable", "staging", ...)
    accept_uploads = Column(Boolean(), default=False)

    new_policy = Column(Enum(NewPolicy), default=NewPolicy.DEFAULT)  # Policy how new packages should be processed

    # Whether this is a development target suite ("testing", "green", ...)
    devel_target = Column(Boolean(), default=False)
    frozen = Column(Boolean(), default=False)  # Whether the suite is frozen and immutable for changes
    auto_overrides = Column(Boolean(), default=False)  # Automatically process overrides, no package will land in NEW
    # Every package will end up in the NEW queue for manual review, no automatic ACCEPT will happen
    manual_accept = Column(Boolean(), default=False)

    # If set, packages from this source will not be installed automatically
    not_automatic = Column(Boolean(), default=False)
    # Packages will not be auto-installed, but auto-upgraded if already installed
    but_automatic_upgrades = Column(Boolean(), default=False)

    valid_time = Column(Integer, default=604800)  # time in seconds how long the suite index should be considered valid
    # delay before a package is available to 100% of all users (0 to disable phased updates)
    phased_update_delay = Column(Integer, default=0)
    signingkeys = Column(
        ARRAY(String(64))
    )  # Fingerprints of GPG keys the suite will be signed with in the respective repo
    announce_emails = Column(ARRAY(Text()))  # E-Mail addresses that changes to this repository should be announced at

    changes_pending = Column(Boolean(), default=True)  # whether the suite in this repository has unpublished changes
    time_published = Column(
        DateTime(), default=datetime.utcfromtimestamp(0)
    )  # Time when this repo/suite configuration was last published

    def __init__(self, repo: ArchiveRepository, suite: ArchiveSuite):
        if repo.is_debug and suite.dbgsym_policy != DbgSymPolicy.ONLY_DEBUG:
            raise ValueError(
                'Debug-Type values of suite and repository do not fit: Suite is debug={}, while repo is debug={}'.format(
                    str(suite.dbgsym_policy), repo.is_debug
                )
            )
        self.repo_id = repo.id
        self.suite_id = suite.id


class ArchiveComponent(Base):
    """
    Information about an archive component within a suite.
    """

    __tablename__ = 'archive_components'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    summary = Column(String(200), nullable=True)  # Short explanation of this component's purpose

    suites = relationship('ArchiveSuite', secondary=suite_component_assoc_table, back_populates='components')

    parent_component_id = Column(Integer, ForeignKey('archive_components.id'))
    # Other components that need to be present to fulfill dependencies of packages in this component
    parent_component = relationship('ArchiveComponent', remote_side=[id])

    def __init__(self, name):
        self.name = name

    def is_primary(self):
        return self.name == 'main'

    def is_nonfree(self):
        return self.name == 'non-free'


class ArchiveArchitecture(Base):
    """
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    """

    __tablename__ = 'archive_architectures'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the architecture
    summary = Column(String(200))  # Short description of this architecture

    suites = relationship(
        'ArchiveSuite', secondary=suite_arch_assoc_table, back_populates='architectures'
    )  # Suites that contain this architecture

    pkgs_binary = relationship('BinaryPackage', back_populates='architecture', cascade=None)

    def __init__(self, name):
        self.name = name


class ArchiveSection(Base):
    """
    Known sections in the archive that packages are sorted into.
    See https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections for reference.
    """

    __tablename__ = 'archive_sections'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the section
    summary = Column(String(200), nullable=True)  # Short description of this section

    def __init__(self, name: str, summary: str = None):
        self.name = name
        self.summary = summary


class ArchiveQueueNewEntry(Base):
    """
    Queue for package NEW processing.
    """

    __tablename__ = 'archive_queue_new'

    id = Column(Integer, primary_key=True)

    package_uuid = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'))
    package = relationship('SourcePackage')

    destination_id = Column(Integer, ForeignKey('archive_suites.id'))
    destination = relationship('ArchiveSuite')

    comment = Column(Text(), nullable=True)


class PackageType(enum.Enum):
    """
    Type of the package.
    """

    UNKNOWN = 0
    SOURCE = enum.auto()
    BINARY = enum.auto()


class DebType(enum.IntEnum):
    """
    Type of the Debian package.
    """

    UNKNOWN = 0
    DEB = enum.auto()
    UDEB = enum.auto()

    @staticmethod
    def to_string(e):
        if e == DebType.DEB:
            return 'deb'
        elif e == DebType.UDEB:
            return 'udeb'
        return 'unknown'

    def __str__(self):
        return DebType.to_string(self)

    @staticmethod
    def from_string(s: str) -> 'DebType':
        """
        Convert the text representation into the enumerated type.
        """
        if s == 'deb':
            return DebType.DEB
        elif s == 'udeb':
            return DebType.UDEB
        return DebType.UNKNOWN


class PackagePriority(enum.IntEnum):
    """
    Priority of a Debian package.
    """

    UNKNOWN = 0
    REQUIRED = enum.auto()
    IMPORTANT = enum.auto()
    STANDARD = enum.auto()
    OPTIONAL = enum.auto()
    EXTRA = enum.auto()

    @staticmethod
    def to_string(e):
        if e == PackagePriority.OPTIONAL:
            return 'optional'
        if e == PackagePriority.EXTRA:
            return 'extra'
        if e == PackagePriority.STANDARD:
            return 'standard'
        if e == PackagePriority.IMPORTANT:
            return 'important'
        if e == PackagePriority.REQUIRED:
            return 'required'
        return 'invalid'

    def __str__(self):
        return PackagePriority.to_string(self)

    @staticmethod
    def from_string(s: str) -> 'PackagePriority':
        """
        Convert the text representation into the enumerated type.
        """
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


class ChangesUrgency(enum.Enum):
    """
    Urgency for how important it is to upgrade to a new package version
    from previous ones.
    https://www.debian.org/doc/debian-policy/ch-controlfields.html#urgency
    """

    UNKNOWN = 0
    LOW = enum.auto()
    MEDIUM = enum.auto()
    HIGH = enum.auto()
    CRITICAL = enum.auto()
    EMERGENCY = enum.auto()

    def to_string(self):
        if self.value == self.LOW.value:
            return 'low'
        elif self.value == self.MEDIUM.value:
            return 'medium'
        elif self.value == self.HIGH.value:
            return 'high'
        elif self.value == self.CRITICAL.value:
            return 'critical'
        elif self.value == self.EMERGENCY.value:
            return 'emergency'
        return 'unknown'

    @staticmethod
    def from_string(s: str) -> 'ChangesUrgency':
        """
        Convert the text representation into the enumerated type.
        """
        if s == 'low':
            return ChangesUrgency.LOW
        elif s == 'medium':
            return ChangesUrgency.MEDIUM
        elif s == 'high':
            return ChangesUrgency.HIGH
        elif s == 'critical':
            return ChangesUrgency.CRITICAL
        elif s == 'emergency':
            return ChangesUrgency.EMERGENCY
        return ChangesUrgency.UNKNOWN

    def __str__(self):
        return self.to_string()


@dataclass
class PackageInfo:
    """
    Basic package information, used by
    :SourcePackage to refer to binary packages.
    """

    deb_type: DebType = DebType.DEB
    name: str = None
    version: str = None
    component: str = 'main'
    section: str = None
    essential: bool = False
    priority: PackagePriority = PackagePriority.UNKNOWN
    architectures: T.List[str] = None


class ArchiveFile(Base):
    """
    A file in the archive.
    """

    __tablename__ = 'archive_files'
    __table_args__ = (UniqueConstraint('repo_id', 'fname', name='_repo_fname_uc'),)

    id = Column(Integer, primary_key=True)

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo = relationship('ArchiveRepository')

    fname = Column(Text(), nullable=False)
    size = Column(BigInteger())  # the size of the file
    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this file was created

    md5sum = Column(CHAR(32))  # the files' MD5 checksum
    sha1sum = Column(CHAR(40))  # the files' SHA1 checksum
    sha256sum = Column(CHAR(64))  # the files' SHA256 checksum
    sha512sum = Column(CHAR(128))  # the files' SHA512 checksum

    pkgs_source = relationship('SourcePackage', secondary=srcpkg_file_assoc_table, back_populates='files')
    pkg_binary = relationship('BinaryPackage', back_populates='bin_file')

    def __init__(self, fname: T.Union[Path, str], repo: ArchiveRepository = None):
        self.fname = str(fname)
        if repo:
            self.repo = repo

    def make_url(self, urlbase):
        if urlbase[-1] == '/':
            return urlbase + str(self.fname)
        else:
            return urlbase + '/' + str(self.fname)


class SourcePackage(Base):
    """
    Data of a source package.
    """

    __tablename__ = 'archive_pkgs_source'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)

    # The unique identifier for the whole source packaging project (stays the same even if the package version changes)
    source_uuid = Column(UUID(as_uuid=True), default=None, nullable=False)

    name = Column(String(200))  # Source package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo = relationship('ArchiveRepository')

    suites = relationship(
        'ArchiveSuite', secondary=srcpkg_suite_assoc_table, back_populates='pkgs_source'
    )  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'), nullable=False)
    component = relationship('ArchiveComponent')  # Component this package is in

    time_added = Column(DateTime(), default=datetime.utcnow)  # Time when this package was first seen
    time_published = Column(DateTime(), nullable=True)  # Time when this package was published in the archive
    time_deleted = Column(DateTime(), nullable=True)  # Time when this package was deleted from the archive

    section_id = Column(Integer, ForeignKey('archive_sections.id'))
    section = relationship('ArchiveSection')  # Section of the source package

    architectures = Column(ARRAY(String(64)))  # List of architectures this source package can be built for

    standards_version = Column(String(256), nullable=True)
    format_version = Column(String(64))

    maintainer = Column(Text())
    original_maintainer = Column(Text(), nullable=True)
    uploaders = Column(ARRAY(Text()))

    homepage = Column(Text(), nullable=True)  # homepage URL of this package
    vcs_browser = Column(Text(), nullable=True)  # VCS browser URL
    vcs_git = Column(Text(), nullable=True)  # Git repository URL

    summary = Column(Text(), nullable=True)
    description = Column(Text(), nullable=True)

    testsuite = Column(ARRAY(String(100)))  # list of testsuite types this package contains
    testsuite_triggers = Column(ARRAY(String(200)))  # list of package names that trigger the testsuite

    # value for how important it is to upgrade to this package version from previous ones
    changes_urgency = Column(Enum(ChangesUrgency), default=ChangesUrgency.MEDIUM)

    # see https://www.debian.org/doc/debian-policy/ch-relationships.html
    build_depends = Column(ARRAY(Text()))
    build_depends_indep = Column(ARRAY(Text()))
    build_depends_arch = Column(ARRAY(Text()))

    build_conflicts = Column(ARRAY(Text()))
    build_conflicts_indep = Column(ARRAY(Text()))
    build_conflicts_arch = Column(ARRAY(Text()))

    directory = Column(Text(), nullable=False)  # pool directory name for the sources
    files = relationship(
        'ArchiveFile', secondary=srcpkg_file_assoc_table, back_populates='pkgs_source'
    )  # Files that make this source package

    binaries = relationship('BinaryPackage', back_populates='source', uselist=True)

    _expected_binaries_json = Column('expected_binaries', JSON)
    # Additional key-value metadata that may be specific to this package
    extra_data = Column(MutableDict.as_mutable(JSONB), default={})

    _expected_binaries = None

    def __init__(self, name: str, version: str, repo: ArchiveRepository = None):
        self.name = name
        self.version = version
        if repo:
            self.repo = repo
            self.update_uuid()

    @property
    def dsc_file(self) -> T.Optional[ArchiveFile]:
        for f in self.files:
            if f.fname.endswith('.dsc'):
                return f
        return None

    @property
    def expected_binaries(self):
        if self._expected_binaries is not None:
            return self._expected_binaries
        data = json.loads(self._expected_binaries_json)
        res = []
        for e in data:
            info = PackageInfo()
            info.deb_type = e.get('deb_type', DebType.DEB)
            info.name = e.get('name')
            info.version = e.get('version')
            info.section = e.get('section')
            info.essential = e.get('essential', False)
            info.priority = e.get('priority', PackagePriority.UNKNOWN)
            info.architectures = e.get('architectures')
            res.append(info)
        self._expected_binaries = res
        return res

    @expected_binaries.setter
    def expected_binaries(self, value):
        if not type(value) is list:
            value = [value]

        data = []
        for v in value:
            d = {
                'deb_type': v.deb_type,
                'name': v.name,
                'version': v.version,
                'section': v.section,
                'priority': v.priority,
                'architectures': v.architectures,
            }
            if v.essential:
                d['essential'] = True
            data.append(d)
        self._expected_binaries_json = json.dumps(data)
        self._expected_binaries = None  # Force the data to be re-loaded from JSON

    @staticmethod
    def generate_uuid(repo_name, name, version):
        return uuid.uuid5(UUID_NS_SRCPACKAGE, '{}:source/{}/{}'.format(repo_name, name, version))

    @staticmethod
    def generate_source_uuid(repo_name, name):
        return uuid.uuid5(UUID_NS_SRCPACKAGE, '{}:source/{}'.format(repo_name, name))

    def update_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.update_source_uuid()
        self.uuid = SourcePackage.generate_uuid(self.repo.name, self.name, self.version)

        return self.uuid

    def update_source_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.source_uuid = SourcePackage.generate_source_uuid(self.repo.name, self.name)
        return self.source_uuid

    def mark_remove(self):
        """Mark this source package for removal during next maintenance run."""
        self.time_deleted = datetime.utcnow()

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        return '{}:source/{}/{}'.format(repo_name, self.name, self.version)


class ArchiveVersionMemory(Base):
    """
    Remember the highest version number for a source package that a repository has seen.
    """

    __tablename__ = 'archive_pkg_version_memory'
    __table_args__ = (UniqueConstraint('pkgname', 'repo_id', name='_pkgname_repo_uc'),)

    id = Column(Integer, primary_key=True)

    pkgname = Column(String(200))  # Name of the source package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    highest_version = Column(DebVersion())  # Highest version of the source package that we have seen so far


class PackageOverride(Base):
    """
    Overridable "archive organization" data of a binary package.
    """

    __tablename__ = 'archive_pkg_overrides'

    id = Column(Integer, primary_key=True)

    pkgname = Column(String(200))  # Name of the binary package

    repo_suite_id = Column(Integer, ForeignKey('archive_repo_suite_settings.id'))
    repo_suite = relationship('ArchiveRepoSuiteSettings')

    essential = Column(Boolean(), default=False)  # Whether this package is marked as essential
    priority = Column(Enum(PackagePriority))  # Priority of the package

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this override is for

    section_id = Column(Integer, ForeignKey('archive_sections.id'))
    section = relationship('ArchiveSection')  # Section of the package

    package = relationship('BinaryPackage', back_populates='override')

    def __init__(self, pkgname: str):
        self.pkgname = pkgname


class BinaryPackage(Base):
    """
    Data of a binary package.
    """

    __tablename__ = 'archive_pkgs_binary'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)
    deb_type = Column(Enum(DebType), default=DebType.DEB)  # Deb package type

    name = Column(String(200))  # Package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')  # Repository this package belongs to

    suites = relationship(
        'ArchiveSuite', secondary=binpkg_suite_assoc_table, back_populates='pkgs_binary'
    )  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this package is in

    architecture_id = Column(Integer, ForeignKey('archive_architectures.id'))
    # Architecture this binary was built for
    architecture = relationship('ArchiveArchitecture', back_populates='pkgs_binary', cascade=None)

    source_id = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'))
    source = relationship('SourcePackage', back_populates='binaries')

    override_id = Column(Integer, ForeignKey('archive_pkg_overrides.id'))
    override = relationship('PackageOverride', back_populates='package')  # Override data for this binary

    time_added = Column(DateTime(), default=datetime.utcnow)  # Time when this package was added to the archive
    time_published = Column(DateTime(), nullable=True)  # Time when this package was published in the archive
    time_deleted = Column(DateTime(), nullable=True)  # Time when this package was deleted from the archive

    size_installed = Column(BigInteger())  # Size of the installed package

    summary = Column(Text())
    description = Column(Text())
    description_md5 = Column(CHAR(32))

    depends = Column(ARRAY(Text()))
    pre_depends = Column(ARRAY(Text()))

    replaces = Column(ARRAY(Text()))
    provides = Column(ARRAY(Text()))
    recommends = Column(ARRAY(Text()))
    suggests = Column(ARRAY(Text()))
    enhances = Column(ARRAY(Text()))
    conflicts = Column(ARRAY(Text()))
    breaks = Column(ARRAY(Text()))

    built_using = Column(ARRAY(Text()))
    static_built_using = Column(ARRAY(Text()))

    build_ids = Column(ARRAY(Text()))

    maintainer = Column(Text())
    original_maintainer = Column(Text(), nullable=True)
    homepage = Column(Text())

    multi_arch = Column(CHAR(32))

    phased_update_percentage = Column(SmallInteger(), default=100)

    contents = Column(ARRAY(Text()))  # List of filenames that this package contains

    # Additional key-value metadata that may be specific to this package
    extra_data = Column(MutableDict.as_mutable(JSONB), default={})

    bin_file_id = Column(Integer, ForeignKey('archive_files.id'))
    bin_file = relationship(
        'ArchiveFile', back_populates='pkg_binary', cascade='all, delete, delete-orphan', single_parent=True
    )
    sw_cpts = relationship('SoftwareComponent', secondary=swcpt_binpkg_assoc_table, back_populates='pkgs_binary')

    __ts_vector__ = create_tsvector(cast(func.coalesce(name, ''), TEXT), cast(func.coalesce(description, ''), TEXT))

    __table_args__ = (Index('idx_bin_package_fts', __ts_vector__, postgresql_using='gin'),)

    def __init__(self, name: str, version: str, repo: ArchiveRepository = None):
        self.name = name
        self.version = version
        if repo:
            self.repo = repo

    @property
    def directory(self) -> str:
        from laniakea.archive.utils import pool_dir_from_name_component

        return pool_dir_from_name_component(self.source.name, self.component.name)

    @staticmethod
    def generate_uuid(repo_name, name, version, arch_name):
        return uuid.uuid5(UUID_NS_BINPACKAGE, '{}:{}/{}/{}'.format(repo_name, name, version, arch_name))

    def update_uuid(self):
        if not self.repo:
            raise Exception('Binary package is not associated with a repository!')

        self.uuid = BinaryPackage.generate_uuid(self.repo.name, self.name, self.version, self.architecture.name)
        return self.uuid

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        arch_name = 'unknown'
        if self.architecture:
            arch_name = self.architecture.name
        return '{}:{}/{}/{}'.format(repo_name, self.name, self.version, arch_name)


# Index to speed up data exports, where packages belonging to a certain repository/arch
# combination are requested.
pkgs_binary_repo_arch_index = Index('idx_pkgs_binary_repo_arch', BinaryPackage.repo_id, BinaryPackage.architecture_id)


class SoftwareComponent(Base):
    """
    Description of a software component as described by the AppStream
    specification.
    """

    __tablename__ = 'archive_sw_components'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kind = Column(Integer())  # The component type

    cid = Column(Text(), nullable=False)  # The component ID of this software
    gcid = Column(Text(), nullable=False)  # The global component ID as used by appstream-generator

    name = Column(Text(), nullable=False)  # Name of this component
    summary = Column(Text())  # Short description of this component
    description = Column(Text())  # Description of this component

    icon_name = Column(String(200))  # Name of the primary cached icon of this component

    is_free = Column(Boolean(), default=False)  # Whether this component is "free as in freedom" software
    project_license = Column(Text())  # License of this software
    developer_name = Column(Text())  # Name of the developer of this software

    supports_touch = Column(Boolean(), default=False)  # Whether this component supports touch input

    categories = Column(ARRAY(String(100)))  # Categories this component is in

    pkgs_binary = relationship(
        'BinaryPackage',
        secondary=swcpt_binpkg_assoc_table,
        order_by='desc(BinaryPackage.version)',
        back_populates='sw_cpts',
    )  # Packages this software component is contained in

    flatpakref_uuid = Column(UUID(as_uuid=True), ForeignKey('flatpak_refs.uuid'))
    flatpakref = relationship('FlatpakRef')

    _data = Column('data', JSON)  # JSON representation of AppStream's collection data for this component

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(summary, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT),
    )

    __table_args__ = (Index('idx_sw_components_fts', __ts_vector__, postgresql_using='gin'),)

    def update_uuid(self):
        """
        Update the unique identifier for this component.
        """
        if not self.gcid:
            raise Exception('Global component ID is not set for this component. Can not create UUID.')

        self.uuid = uuid.uuid5(UUID_NS_SWCOMPONENT, self.gcid)
        return self.uuid

    @property
    def data(self) -> T.Dict[str, T.Any]:
        return json.loads(self._data)

    @data.setter
    def data(self, value: T.Union[str, bytes, T.Dict[str, T.Any]]):
        if type(value) is bytes or type(value) is str:
            self._data = value
        elif type(value) is dict:
            self._data = json.dumps(value)
        else:
            raise ValueError('Can not add {} ({}) as software component data value.'.format(type(value), str(value)))
