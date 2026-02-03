# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2024 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import enum
import json
import uuid
from pathlib import Path
from datetime import UTC, datetime
from dataclasses import dataclass

import apt_pkg
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
from sqlalchemy.orm import Mapped, backref, relationship, mapped_column
from sqlalchemy.sql import cast, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import CHAR, JSON, TEXT, ARRAY, JSONB

import laniakea.typing as T

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    primary_repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'))
    primary_repo: Mapped['ArchiveRepository'] = relationship('ArchiveRepository')
    auto_debug_management: Mapped[bool] = mapped_column(Boolean(), default=True)
    primary_repo_root: Mapped[str] = mapped_column(Text(), nullable=False, default='/')
    extra_repo_root: Mapped[str] = mapped_column(Text(), nullable=False, default='/multiverse')
    archive_url: Mapped[str] = mapped_column(Text(), nullable=False)


class ArchiveRepository(Base):
    """
    A repository of packages.
    """

    __tablename__ = 'archive_repositories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(100), unique=True)
    origin_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_debug: Mapped[bool] = mapped_column(Boolean(), default=False)

    debug_repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=True)
    debug_repo_for: Mapped['ArchiveRepository'] = relationship(
        'ArchiveRepository', backref=backref('debug_repo', remote_side=[id]), uselist=False
    )

    uploaders: Mapped[list['ArchiveUploader']] = relationship(
        'ArchiveUploader', secondary=uploader_repo_assoc_table, back_populates='repos'
    )

    suite_settings: Mapped[list['ArchiveRepoSuiteSettings']] = relationship(
        'ArchiveRepoSuiteSettings', back_populates='repo', uselist=True, cascade='all, delete, delete-orphan'
    )

    upload_suite_map: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON()), default={})

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
        ForeignKey('software_components.uuid', ondelete='cascade'),
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    email: Mapped[str] = mapped_column(Text(), unique=True)  # E-Mail address of this entity used for signing
    pgp_fingerprints: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), default=[]
    )  # Fingerprints of the GnuPG keys associated with this entity
    is_human: Mapped[bool] = mapped_column(
        Boolean(), default=True
    )  # Whether this entry applies to a human person or a machine

    name: Mapped[str] = mapped_column(Text(), nullable=True)  # Full name of this uploader
    alias: Mapped[str] = mapped_column(Text(), nullable=True)  # Alias or nickname of this uploader

    allow_source_uploads: Mapped[bool] = mapped_column(Boolean(), default=True)  # Whether source uploads are permitted
    allow_binary_uploads: Mapped[bool] = mapped_column(
        Boolean(), default=True
    )  # Whether binary package uploads are permitted
    allow_flatpak_uploads: Mapped[bool] = mapped_column(
        Boolean(), default=True
    )  # Whether binary Flatpak bundle uploads are permitted

    # Whether uploads of this entity should always end up in the NEW queue
    always_review: Mapped[bool] = mapped_column(Boolean(), default=False)
    # Names of source packages that this entity is allowed to touch, empty to allow all
    allowed_packages: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    repos: Mapped[list['ArchiveRepository']] = relationship(
        'ArchiveRepository', secondary=uploader_repo_assoc_table, back_populates='uploaders'
    )

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(120), unique=True)  # Name of the suite, usually the codename e.g. "sid"
    alias: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=True
    )  # Alternative name of the suite, e.g. "unstable"
    summary: Mapped[str] = mapped_column(String(200), nullable=True)  # Short description string for this suite
    version: Mapped[str] = mapped_column(String(80), nullable=True)  # Version string applicable for this suite
    dbgsym_policy: Mapped[DbgSymPolicy] = mapped_column(
        Enum(DbgSymPolicy), default=DbgSymPolicy.NO_DEBUG
    )  # Set how debug symbol packages should be handled for this suite

    architectures: Mapped[list['ArchiveArchitecture']] = relationship(
        'ArchiveArchitecture', secondary=suite_arch_assoc_table, back_populates='suites'
    )
    components: Mapped[list['ArchiveComponent']] = relationship(
        'ArchiveComponent', secondary=suite_component_assoc_table, back_populates='suites'
    )

    debug_suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=True)
    debug_suite_for: Mapped['ArchiveSuite | None'] = relationship(
        'ArchiveSuite', backref=backref('debug_suite', remote_side='ArchiveSuite.id'), uselist=False
    )

    # Type annotation for the backref-created attribute (for MyPy)
    if T.TYPE_CHECKING:
        debug_suite: Mapped['ArchiveSuite | None']

    repo_settings: Mapped[list['ArchiveRepoSuiteSettings']] = relationship(
        'ArchiveRepoSuiteSettings', back_populates='suite', cascade='all, delete, delete-orphan'
    )

    parents: Mapped[list['ArchiveSuite']] = relationship(
        'ArchiveSuite',
        secondary=suite_parents_assoc_table,
        primaryjoin=id == suite_parents_assoc_table.c.suite_id,
        secondaryjoin=id == suite_parents_assoc_table.c.parent_suite_id,
        backref='overlays',
    )

    pkgs_source: Mapped[list['SourcePackage']] = relationship(
        'SourcePackage', secondary=srcpkg_suite_assoc_table, back_populates='suites'
    )
    pkgs_binary: Mapped[list['BinaryPackage']] = relationship(
        'BinaryPackage', secondary=binpkg_suite_assoc_table, back_populates='suites'
    )

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped['ArchiveRepository'] = relationship('ArchiveRepository', back_populates='suite_settings')

    suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=False)
    suite: Mapped['ArchiveSuite'] = relationship('ArchiveSuite', back_populates='repo_settings')

    suite_summary: Mapped[str] = mapped_column(String(200), nullable=True)
    accept_uploads: Mapped[bool] = mapped_column(Boolean(), default=False)
    new_policy: Mapped[NewPolicy] = mapped_column(Enum(NewPolicy), default=NewPolicy.DEFAULT)
    devel_target: Mapped[bool] = mapped_column(Boolean(), default=False)
    frozen: Mapped[bool] = mapped_column(Boolean(), default=False)
    auto_overrides: Mapped[bool] = mapped_column(Boolean(), default=False)
    manual_accept: Mapped[bool] = mapped_column(Boolean(), default=False)
    not_automatic: Mapped[bool] = mapped_column(Boolean(), default=False)
    but_automatic_upgrades: Mapped[bool] = mapped_column(Boolean(), default=False)
    valid_time: Mapped[int] = mapped_column(Integer, default=604800)
    phased_update_delay: Mapped[int] = mapped_column(Integer, default=0)
    signingkeys: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=[])
    announce_emails: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    changes_pending: Mapped[bool] = mapped_column(Boolean(), default=True)
    time_published: Mapped[datetime] = mapped_column(DateTime(), default=datetime.fromtimestamp(0, UTC))

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(100), unique=True)  # Name of the repository
    summary: Mapped[str] = mapped_column(String(200), nullable=True)  # Short explanation of this component's purpose

    suites: Mapped[list['ArchiveSuite']] = relationship(
        'ArchiveSuite', secondary=suite_component_assoc_table, back_populates='components'
    )

    parent_component_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_components.id'), nullable=True)
    # Other components that need to be present to fulfill dependencies of packages in this component
    parent_component: Mapped['ArchiveComponent'] = relationship('ArchiveComponent', remote_side=[id])

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(80), unique=True)  # Name of the architecture
    summary: Mapped[str] = mapped_column(String(200))  # Short description of this architecture

    suites: Mapped[list['ArchiveSuite']] = relationship(
        'ArchiveSuite', secondary=suite_arch_assoc_table, back_populates='architectures'
    )  # Suites that contain this architecture

    pkgs_binary: Mapped[list['BinaryPackage']] = relationship(
        'BinaryPackage', back_populates='architecture', cascade=None
    )

    def __init__(self, name):
        self.name = name


class ArchiveSection(Base):
    """
    Known sections in the archive that packages are sorted into.
    See https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections for reference.
    """

    __tablename__ = 'archive_sections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)  # Unique name/ID of the section
    title: Mapped[str] = mapped_column(String(100), nullable=False)  # Title of the section
    summary: Mapped[str] = mapped_column(Text(), nullable=True)  # Short description of this section

    def __init__(self, name: str, title: str, summary: str = None):
        self.name = name
        self.title = title
        self.summary = summary


class ArchiveQueueNewEntry(Base):
    """
    Queue for package NEW processing.
    """

    __tablename__ = 'archive_queue_new'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    package_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'), nullable=False
    )
    package: Mapped['SourcePackage'] = relationship('SourcePackage')

    destination_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=False)
    destination: Mapped['ArchiveSuite'] = relationship('ArchiveSuite')

    comment: Mapped[str] = mapped_column(Text(), nullable=True)

    def __init__(self, spkg: 'SourcePackage', dest: 'ArchiveSuite'):
        self.package = spkg
        self.destination = dest


class PackageType(enum.Enum):
    """
    Type of the package.
    """

    UNKNOWN = 0
    SOURCE = enum.auto()
    BINARY = enum.auto()

    @staticmethod
    def to_string(e):
        if e == PackageType.SOURCE:
            return 'source'
        elif e == PackageType.BINARY:
            return 'binary'
        return 'unknown'

    def __str__(self):
        return PackageType.to_string(self)

    @staticmethod
    def from_string(s: str) -> 'PackageType':
        """
        Convert the text representation into the enumerated type.
        """
        if s == 'source':
            return PackageType.SOURCE
        elif s == 'binary':
            return PackageType.BINARY
        return PackageType.UNKNOWN


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped['ArchiveRepository'] = relationship('ArchiveRepository')

    fname: Mapped[str] = mapped_column(Text(), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger())  # the size of the file
    time_created: Mapped[datetime] = mapped_column(
        DateTime(), default=datetime.utcnow
    )  # Time when this file was created

    md5sum: Mapped[str] = mapped_column(CHAR(32))  # the files' MD5 checksum
    sha1sum: Mapped[str] = mapped_column(CHAR(40))  # the files' SHA1 checksum
    sha256sum: Mapped[str] = mapped_column(CHAR(64))  # the files' SHA256 checksum
    sha512sum: Mapped[str] = mapped_column(CHAR(128))  # the files' SHA512 checksum

    pkgs_source: Mapped[list['SourcePackage']] = relationship(
        'SourcePackage', secondary=srcpkg_file_assoc_table, back_populates='files'
    )
    pkg_binary: Mapped['BinaryPackage'] = relationship('BinaryPackage', back_populates='bin_file')

    def __init__(self, fname: T.Union[Path, str], repo: ArchiveRepository = None):
        self.fname = str(fname)
        if repo:
            self.repo = repo

    def make_url(self, urlbase):
        if urlbase[-1] == '/':
            return urlbase + str(self.fname)
        else:
            return urlbase + '/' + str(self.fname)

    @property
    def absolute_repo_path(self) -> T.PathUnion:
        """Absolute path to the file in its repository.

        NOTE: Files may also be in the queue directory of a repository, if they are
        pending review.
        """
        return os.path.join(self.repo.get_root_dir(), self.fname)


class SourcePackage(Base):
    """
    Data of a source package.
    """

    __tablename__ = 'archive_pkgs_source'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)

    # The unique identifier for the whole source packaging project (stays the same even if the package version changes)
    source_uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), default=None, nullable=False)

    name: Mapped[str] = mapped_column(String(200))  # Source package name
    version: Mapped[str] = mapped_column(DebVersion())  # Version of this package

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped['ArchiveRepository'] = relationship('ArchiveRepository')

    suites: Mapped[list['ArchiveSuite']] = relationship(
        'ArchiveSuite', secondary=srcpkg_suite_assoc_table, back_populates='pkgs_source'
    )  # Suites this package is in

    component_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_components.id'), nullable=False)
    component: Mapped['ArchiveComponent'] = relationship('ArchiveComponent')  # Component this package is in

    time_added: Mapped[datetime] = mapped_column(
        DateTime(), default=datetime.utcnow
    )  # Time when this package was first seen
    time_published: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True
    )  # Time when this package was published in the archive
    time_deleted: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True
    )  # Time when this package was deleted from the archive

    section_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_sections.id'), nullable=True)
    section: Mapped['ArchiveSection'] = relationship('ArchiveSection')  # Section of the source package

    architectures: Mapped[list[str]] = mapped_column(
        ARRAY(String(80))
    )  # List of architectures this source package can be built for

    standards_version: Mapped[str] = mapped_column(String(80), nullable=True)
    format_version: Mapped[str] = mapped_column(String(80))

    maintainer: Mapped[str] = mapped_column(Text())
    original_maintainer: Mapped[str] = mapped_column(Text(), nullable=True)
    uploaders: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    homepage: Mapped[str] = mapped_column(Text(), nullable=True)  # homepage URL of this package
    vcs_browser: Mapped[str] = mapped_column(Text(), nullable=True)  # VCS browser URL
    vcs_git: Mapped[str] = mapped_column(Text(), nullable=True)  # Git repository URL

    summary: Mapped[str] = mapped_column(Text(), nullable=True)
    description: Mapped[str] = mapped_column(Text(), nullable=True)

    testsuite: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=[]
    )  # list of testsuite types this package contains
    testsuite_triggers: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), default=[]
    )  # list of package names that trigger the testsuite

    # value for how important it is to upgrade to this package version from previous ones
    changes_urgency: Mapped[ChangesUrgency] = mapped_column(Enum(ChangesUrgency), default=ChangesUrgency.MEDIUM)

    # see https://www.debian.org/doc/debian-policy/ch-relationships.html
    build_depends: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    build_depends_indep: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    build_depends_arch: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    build_conflicts: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    build_conflicts_indep: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    build_conflicts_arch: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    directory: Mapped[str] = mapped_column(Text(), nullable=False)  # pool directory name for the sources
    files: Mapped[list['ArchiveFile']] = relationship(
        'ArchiveFile', secondary=srcpkg_file_assoc_table, back_populates='pkgs_source'
    )  # Files that make this source package

    binaries: Mapped[list['BinaryPackage']] = relationship('BinaryPackage', back_populates='source', uselist=True)

    _expected_binaries_json: Mapped[str] = mapped_column('expected_binaries', JSON)
    # Additional key-value metadata that may be specific to this package
    extra_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB()), default={})

    _expected_binaries = None

    def __init__(self, name: str, version: str, repo: ArchiveRepository = None):
        self.name = name
        self.version = version
        if repo:
            self.repo = repo
            self.update_uuid()

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        return '{}:source/{}/{}'.format(repo_name, self.name, self.version)

    @property
    def dsc_file(self) -> ArchiveFile | None:
        for f in self.files:
            if f.fname.endswith('.dsc'):
                return f
        return None

    @property
    def expected_binaries(self) -> list[PackageInfo]:
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
    def expected_binaries(self, value: PackageInfo | list[PackageInfo]):
        if not isinstance(value, list):
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

    def get_metadata_dir(self, lconf=None):
        """Get the metadata storage location for this package."""
        from laniakea import LocalConfig

        if not lconf:
            lconf = LocalConfig()
        return os.path.join(lconf.package_metadata_dir, self.repo.name, *Path(self.directory).parts[1:])


# Index to speed up source package searches
idx_pkgs_source_repo_component = Index(
    'idx_pkgs_source_repo_component',
    SourcePackage.repo_id,
    SourcePackage.component_id,
    SourcePackage.time_deleted,
)

idx_pkgs_source_repo_name_version = Index(
    'idx_pkgs_source_repo_name_version',
    SourcePackage.repo_id,
    SourcePackage.name,
    SourcePackage.version,
)

idx_pkgs_source_source_id_version = Index(
    'idx_pkgs_source_source_id_version',
    SourcePackage.source_uuid,
    SourcePackage.version,
)


class ArchiveVersionMemory(Base):
    """
    Remember the highest version number for a source package that a repository has seen.
    """

    __tablename__ = 'archive_pkg_version_memory'
    __table_args__ = (UniqueConstraint('repo_suite_id', 'pkg_name', 'arch_name', name='_rss_pkg_uc'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repo_suite_settings.id'), nullable=False)
    repo_suite: Mapped['ArchiveRepoSuiteSettings'] = relationship('ArchiveRepoSuiteSettings')

    pkg_name: Mapped[str] = mapped_column(String(200), nullable=False)  # Name of the package
    arch_name: Mapped[str] = mapped_column(
        String(80), nullable=False, default='source'
    )  # Architecture identifier name, such as "amd64" or "source"

    highest_version: Mapped[DebVersion] = mapped_column(
        DebVersion()
    )  # Highest version of the source package that we have seen so far


class PackageOverride(Base):
    """
    Overridable "archive organization" data of a binary package.
    """

    __tablename__ = 'archive_pkg_overrides'
    __table_args__ = (UniqueConstraint('repo_id', 'suite_id', 'pkg_name', name='_repo_suite_pkgname_uc'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped['ArchiveRepository'] = relationship(
        'ArchiveRepository', cascade=None
    )  # Repository this override belongs to

    suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=False)
    suite: Mapped['ArchiveSuite'] = relationship('ArchiveSuite', cascade=None)  # Suite this override belongs to

    pkg_name: Mapped[str] = mapped_column(String(200))  # Name of the binary package this override belongs to

    essential: Mapped[bool] = mapped_column(Boolean(), default=False)  # Whether this package is marked as essential
    priority: Mapped[PackagePriority] = mapped_column(
        Enum(PackagePriority), default=PackagePriority.OPTIONAL
    )  # Priority of the package

    component_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_components.id'), nullable=False)
    component: Mapped['ArchiveComponent'] = relationship(
        'ArchiveComponent', cascade=None
    )  # Component this override is for

    section_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_sections.id'), nullable=False)
    section: Mapped['ArchiveSection'] = relationship('ArchiveSection')  # Section of the package

    def __init__(self, pkgname: str, repo: ArchiveRepository, suite: ArchiveSuite):
        self.pkg_name = pkgname
        self.repo = repo
        self.suite = suite


idx_pkgs_binary_repo_arch = Index(
    'idx_overrides_repo_suite_pkgname',
    PackageOverride.repo_id,
    PackageOverride.suite_id,
    PackageOverride.pkg_name,
)


class BinaryPackage(Base):
    """
    Data of a binary package.
    """

    __tablename__ = 'archive_pkgs_binary'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)
    deb_type: Mapped[DebType] = mapped_column(Enum(DebType), default=DebType.DEB)  # Deb package type

    name: Mapped[str] = mapped_column(String(200))  # Package name
    version: Mapped[str] = mapped_column(DebVersion())  # Version of this package

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped['ArchiveRepository'] = relationship(
        'ArchiveRepository', cascade=None
    )  # Repository this package belongs to

    suites: Mapped[list['ArchiveSuite']] = relationship(
        'ArchiveSuite', secondary=binpkg_suite_assoc_table, back_populates='pkgs_binary', cascade=None
    )  # Suites this package is in

    component_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_components.id'), nullable=False)
    component: Mapped['ArchiveComponent'] = relationship(
        'ArchiveComponent', cascade=None
    )  # Component this package is in

    architecture_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_architectures.id'), nullable=False)
    # Architecture this binary was built for
    architecture: Mapped['ArchiveArchitecture'] = relationship(
        'ArchiveArchitecture', back_populates='pkgs_binary', cascade=None
    )

    source_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'), nullable=True)
    source: Mapped['SourcePackage'] = relationship('SourcePackage', back_populates='binaries', cascade='merge')

    time_added: Mapped[datetime] = mapped_column(
        DateTime(), default=datetime.utcnow
    )  # Time when this package was added to the archive
    time_published: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True
    )  # Time when this package was published in the archive
    time_deleted: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True
    )  # Time when this package was deleted from the archive

    size_installed: Mapped[int] = mapped_column(BigInteger())  # Size of the installed package

    summary: Mapped[str] = mapped_column(Text())
    description: Mapped[str] = mapped_column(Text())
    description_md5: Mapped[str] = mapped_column(CHAR(32))

    depends: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    pre_depends: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    replaces: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    provides: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    recommends: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    suggests: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    enhances: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    conflicts: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    breaks: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    built_using: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])
    static_built_using: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    build_ids: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])

    maintainer: Mapped[str] = mapped_column(Text())
    original_maintainer: Mapped[str] = mapped_column(Text(), nullable=True)
    homepage: Mapped[str] = mapped_column(Text(), nullable=True)

    multi_arch: Mapped[str] = mapped_column(String(40), nullable=True)

    phased_update_percentage: Mapped[int] = mapped_column(SmallInteger(), default=100)

    contents: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), default=[]
    )  # List of filenames that this package contains

    # Additional key-value metadata that may be specific to this package
    extra_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB()), default={})

    bin_file_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_files.id'), nullable=True)
    bin_file: Mapped['ArchiveFile'] = relationship(
        'ArchiveFile', back_populates='pkg_binary', cascade='all, delete, delete-orphan', single_parent=True
    )
    sw_cpts: Mapped[list['SoftwareComponent']] = relationship(
        'SoftwareComponent',
        secondary=swcpt_binpkg_assoc_table,
        back_populates='pkgs_binary',
    )

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
idx_pkgs_binary_repo_arch = Index(
    'idx_pkgs_binary_repo_component_arch',
    BinaryPackage.repo_id,
    BinaryPackage.component_id,
    BinaryPackage.architecture_id,
    BinaryPackage.time_deleted,
)

idx_pkgs_binary_repo_name_version = Index(
    'idx_pkgs_binary_repo_name_version',
    BinaryPackage.repo_id,
    BinaryPackage.name,
    BinaryPackage.version,
)

idx_pkgs_binary_repo_source_arch = Index(
    'idx_pkgs_binary_repo_source_arch',
    BinaryPackage.repo_id,
    BinaryPackage.source_id,
    BinaryPackage.architecture_id,
)


def package_version_compare(pkg1: SourcePackage | BinaryPackage, pkg2: SourcePackage | BinaryPackage):
    """Comparison function helper to compare package versions."""
    return apt_pkg.version_compare(pkg1.version, pkg2.version)


class SoftwareComponent(Base):
    """
    Description of a software component as described by the AppStream
    specification.
    """

    __tablename__ = 'software_components'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kind: Mapped[int] = mapped_column(Integer)  # The component type

    cid: Mapped[str] = mapped_column(Text, nullable=False)  # The component ID of this software
    gcid: Mapped[str] = mapped_column(Text, nullable=False)  # The global component ID as used by appstream-generator

    name: Mapped[str] = mapped_column(Text, nullable=False)  # Name of this component
    summary: Mapped[str] = mapped_column(Text)  # Short description of this component
    description: Mapped[str] = mapped_column(Text, nullable=True)  # Description of this component

    icon_name: Mapped[str] = mapped_column(
        String(200), nullable=True
    )  # Name of the primary cached icon of this component

    is_free: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Whether this component is "free as in freedom" software
    project_license: Mapped[str] = mapped_column(Text, nullable=True)  # License of this software
    developer_name: Mapped[str] = mapped_column(Text, nullable=True)  # Name of the developer of this software

    supports_touch: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether this component supports touch input

    categories: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=[])  # Categories this component is in

    pkgs_binary: Mapped[list['BinaryPackage']] = relationship(
        'BinaryPackage',
        secondary=swcpt_binpkg_assoc_table,
        order_by='desc(BinaryPackage.version)',
        back_populates='sw_cpts',
    )  # Packages this software component is contained in

    flatpakref_uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('flatpak_refs.uuid'), nullable=True)
    flatpakref: Mapped['FlatpakRef'] = relationship('FlatpakRef')

    _data: Mapped[str] = mapped_column(
        'data', JSON
    )  # JSON representation of AppStream's collection data for this component

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(summary, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT),
    )

    __table_args__ = (Index('idx_sw_components_fts', __ts_vector__, postgresql_using='gin'),)

    @staticmethod
    def uuid_for_gcid(gcid: str):
        """Create an entity UUID from a component GCID"""
        return uuid.uuid5(UUID_NS_SWCOMPONENT, gcid)

    def update_uuid(self):
        """
        Update the unique identifier for this component.
        """
        if not self.gcid:
            raise Exception('Global component ID is not set for this component. Can not create UUID.')

        self.uuid = SoftwareComponent.uuid_for_gcid(self.gcid)
        return self.uuid

    @property
    def data(self) -> T.Dict[str, T.Any]:
        return json.loads(self._data)

    @data.setter
    def data(self, value: T.Union[str, bytes, T.Dict[str, T.Any]]):
        if type(value) is bytes or type(value) is str:
            self._data = str(value)
        elif type(value) is dict:
            self._data = json.dumps(value)
        else:
            raise ValueError('Can not add {} ({}) as software component data value.'.format(type(value), str(value)))


# late imports to avoid circular dependencies but make linters happy
from laniakea.db.flatpak import FlatpakRef
