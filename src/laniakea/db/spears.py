# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON

from .base import UUID, Base, DebVersion


class SpearsHint(Base):
    '''
    User-defined hints for Britney.
    '''
    __tablename__ = 'spears_hints'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    migration_id = Column(String(256))  # Identifier for the respective migration task, in the form of "source1+source2-to-target"

    time = Column(DateTime(), default=datetime.utcnow)  # Time when this hint was created
    hint = Column(Text())  # A Britney hint
    reason = Column(Text())  # Reason why the package is blacklisted

    user = Column(String(256))  # Person who created this hint


class SpearsMigrationEntry(Base):
    '''
    Configuration specific for the Spears tool.
    '''
    __tablename__ = 'spears_migrations'

    idname = Column(Text(), primary_key=True, nullable=False)

    source_suites = Column(ARRAY(String(128)))  # Names of the suites packages migrate from
    target_suite = Column(String(128))  # Name of the suite packages migrate to

    delays = Column(JSON)  # Dictionary of VersionPriority --> int

    def source_suites_id(self):
        '''
        Get a string identifying the source suites packages are migrated from.
        '''
        return '+'.join(sorted(self.source_suites))

    def make_migration_id(self):
        '''
        Get a unique identifier for this migration task
        '''
        return '{}-to-{}'.format(self.source_suites_id(), self.target_suite)


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

    source_suites = Column(ARRAY(String(128)))

    time = Column(DateTime(), default=datetime.utcnow)  # Time when this excuse was created

    migration_id = Column(Text(), nullable=False)  # Identifier for the respective migration task, in the form of "source1+source2-to-target"

    suite_target = Column(String(128))  # Target suite of this package
    suite_source = Column(String(128))  # Source suite of this package

    is_candidate = Column(Boolean())  # True if the package is considered for migration at all

    source_package = Column(Text())  # source package that is affected by this excuse
    maintainer = Column(Text())  # name of the maintainer responsible for this package

    age_current = Column(Integer())  # current age of the source package upload
    age_required = Column(Integer())  # minimum required age of the upload

    version_new = Column(DebVersion())  # package version waiting to migrate
    version_old = Column(DebVersion())  # old package version in the target suite

    missing_archs_primary = Column(ARRAY(String(128)))    # list of primary architectures where the package has not been built
    missing_archs_secondary = Column(ARRAY(String(128)))  # list of secondary architectures where the package has not been built

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
        return '{}-{}:{}-{}/{}'.format(self.suite_source, self.suite_target, self.source_package, self.version_new, self.version_old)
