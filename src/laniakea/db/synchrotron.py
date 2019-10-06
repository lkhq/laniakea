# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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
from sqlalchemy import Column, Text, String, DateTime, Enum, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import ARRAY
from uuid import uuid4
from datetime import datetime
from .base import Base, UUID, DebVersion


class SynchrotronSource(Base):
    '''
    Definition of a foreign suite to sync packages from.
    '''
    __tablename__ = 'synchrotron_sources'

    id = Column(Integer, primary_key=True)

    os_name = Column(Text(), nullable=False)  # Name of the source OS (usually "Debian")
    suite_name = Column(String(256), nullable=False, unique=True)
    architectures = Column(ARRAY(String(64)))
    components = Column(ARRAY(String(128)))
    repo_url = Column(Text(), nullable=False)


class SynchrotronConfig(Base):
    '''
    Configuration for automatic synchrotron tasks.
    '''
    __tablename__ = 'synchrotron_config'

    id = Column(Integer, primary_key=True)

    source_id = Column(Integer, ForeignKey('synchrotron_sources.id'))
    source = relationship('SynchrotronSource')

    destination_suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    destination_suite = relationship('ArchiveSuite', backref=backref('synchrotron_configs', cascade='all, delete'))

    sync_enabled = Column(Boolean(), default=True)  # true if syncs should happen
    sync_auto_enabled = Column(Boolean(), default=False)  # true if syncs should happen automatically
    sync_binaries = Column(Boolean(), default=False)  # true if we should also sync binary packages


class SyncBlacklistEntry(Base):
    '''
    Synchrotron blacklist
    '''
    __tablename__ = 'synchrotron_blacklist'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    config_id = Column(Integer, ForeignKey('synchrotron_config.id'))
    config = relationship('SynchrotronConfig', cascade='all, delete')

    pkgname = Column(String(256))  # Name of the blacklisted package
    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when the package was blacklisted
    reason = Column(Text())  # Reason why the package is blacklisted

    user = Column(String(256))  # Person who marked this to be ignored


class SynchrotronIssueKind(enum.IntEnum):
    '''
    Kind of a Synchrotron issue.
    '''
    UNKNOWN = 0
    NONE = 1
    MERGE_REQUIRED = 2
    MAYBE_CRUFT = 3
    SYNC_FAILED = 4
    REMOVAL_FAILED = 5

    def __str__(self):
        if self.value == self.NONE:
            return 'none'
        if self.value == self.MERGE_REQUIRED:
            return 'merge-required'
        if self.value == self.MAYBE_CRUFT:
            return 'maybe-cruft'
        if self.value == self.SYNC_FAILED:
            return 'sync-failed'
        if self.value == self.REMOVAL_FAILED:
            return 'removal-failed'
        return 'SynchrotronIssueKind.' + str(self.name)


class SynchrotronIssue(Base):
    '''
    Hints about why packages are not synchronized with a source distribution/suite.
    '''
    __tablename__ = 'synchrotron_issues'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    config_id = Column(Integer, ForeignKey('synchrotron_config.id'), nullable=False)
    config = relationship('SynchrotronConfig', backref=backref('issues',
                                                               cascade='all, delete'))

    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this excuse was created

    kind = Column(Enum(SynchrotronIssueKind))  # Kind of this issue, and usually also the reason for its existence.

    package_name = Column(String(256))  # Name of the source package that is to be synchronized

    source_suite = Column(String(256))  # Source suite of this package, usually the one in Debian
    target_suite = Column(String(256))  # Target suite of this package, from the target distribution

    source_version = Column(DebVersion())  # package version to be synced
    target_version = Column(DebVersion())  # version of the package in the target suite and repo, to be overriden

    details = Column(Text())  # additional information text about the issue (usually a log excerpt)
