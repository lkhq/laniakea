# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from uuid import uuid4
from typing import Any
from datetime import datetime

from sqlalchemy import (
    Text,
    Table,
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import JSON, ARRAY, JSONB

from .base import UUID, Base, DebVersion
from .archive import ArchiveRepository


class SpearsHint(Base):
    '''
    User-defined hints for Britney.
    '''

    __tablename__ = 'spears_hints'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    migration_id = Column(Integer, ForeignKey('spears_migrations.id'))
    migration_task: 'SpearsMigrationTask' = relationship('SpearsMigrationTask')  # Migration task this hint belongs to

    time = Column(DateTime(), default=datetime.utcnow)  # Time when this hint was created
    hint = Column(Text())  # A Britney hint
    reason = Column(Text())  # Reason why the package is blacklisted

    user = Column(String(256))  # Person who created this hint


spears_migration_src_suite_assoc_table = Table(
    'spears_migration_src_suite_association',
    Base.metadata,
    Column(
        'migration_id',
        Integer,
        ForeignKey('spears_migrations.id'),
        primary_key=True,
    ),
    Column('suite_id', Integer, ForeignKey('archive_suites.id'), primary_key=True),
)


class SpearsMigrationTask(Base):
    """
    Description of a migration task from one or multiple suites to a target.
    """

    __tablename__ = 'spears_migrations'

    id = Column(Integer, primary_key=True)

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: ArchiveRepository = relationship('ArchiveRepository')  # Repository this migration task is valid for

    source_suites = relationship(
        'ArchiveSuite', secondary=spears_migration_src_suite_assoc_table
    )  # The suites packages will migrate from
    target_suite_id = Column(Integer, ForeignKey('archive_suites.id'), nullable=False)
    target_suite = relationship('ArchiveSuite')  # The suite packages migrate to

    delays = Column(MutableDict.as_mutable(JSONB))  # Dictionary of VersionPriority --> int

    __table_args__ = (UniqueConstraint('repo_id', 'target_suite_id', name='repo_target_suite_uc'),)

    @property
    def source_suites_str(self) -> str:
        '''
        Get a string identifying the source suites packages are migrated from.
        '''
        return '+'.join(sorted([s.name for s in self.source_suites]))

    def make_migration_unique_name(self):
        '''
        Get a unique identifier for this migration task
        '''
        return '{}:{}-to-{}'.format(self.repo.name, self.source_suites_str, self.target_suite.name)

    def make_migration_shortname(self) -> str:
        """get a short name for this migration that can be used in file paths."""
        return '{}-to-{}'.format(self.source_suites_str, self.target_suite.name)


class SpearsOldBinaries:
    '''
    List of old binaries of a specific version that a package has left behind.
    '''

    pkg_version: str = ''
    binaries: list[Any] = []


class SpearsExcuse(Base):
    '''
    Data for a package migration excuse, as emitted by Britney
    '''

    __tablename__ = 'spears_excuses'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this excuse was created

    migration_id = Column(Integer, ForeignKey('spears_migrations.id'))
    migration_task = relationship('SpearsMigrationTask')  # Migration task this excuse belongs to

    source_package_id = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'))
    source_package = relationship('SourcePackage')  # source package that is affected by this excuse
    maintainer = Column(Text())  # name of the maintainer responsible for this package

    is_candidate = Column(Boolean(), default=False)  # True if the package is considered for migration at all

    age_current = Column(Integer())  # current age of the source package upload
    age_required = Column(Integer())  # minimum required age of the upload

    version_new = Column(DebVersion())  # package version waiting to migrate
    version_old = Column(DebVersion())  # old package version in the target suite

    # list of primary architectures where the package has not been built
    missing_archs_primary = Column(ARRAY(String(128)))
    # list of secondary architectures where the package has not been built
    missing_archs_secondary = Column(ARRAY(String(128)))

    old_binaries = Column(JSON)  # Superseded cruft binaries that need to be garbage-collected

    blocked_by = Column(ARRAY(Text()))  # packages this package depends on which might prevent migration

    migrate_after = Column(ARRAY(Text()))  # packages queued to migrate before this one
    manual_block = Column(JSON)  # manual explicit block hints given by machines and people

    other = Column(ARRAY(Text()))  # Other reasons for not migrating this package
    log_excerpt = Column(Text())  # an excerpt from the migration log that is relevant to this package

    def get_manual_block_hints(self):
        if not self.manual_block:
            return None
        return dict(self.manual_block)

    def get_old_binaries(self):
        if not self.old_binaries:
            return None

        bins = []
        for entry in self.old_binaries:
            obin = SpearsOldBinaries()
            obin.pkg_version = entry.get('pkg_version')
            obin.binaries = entry.get('binaries')
            bins.append(obin)

        return bins

    def set_old_binaries(self, obins):
        j = []
        if not obins:
            obins = []

        for obin in obins:
            d = {}
            d['pkg_version'] = obin.pkg_version
            d['binaries'] = obin.binaries
            j.append(d)
        self.old_binaries = j

    def make_idname(self):
        return '{}:{}->{}:{}-{}/{}'.format(
            self.migration_task.repo.name,
            self.migration_task.source_suites_str,
            self.migration_task.target_suite.name,
            self.source_package.name,
            self.version_new,
            self.version_old,
        )
