# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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
from sqlalchemy import Column, Text, String, Integer, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import text as sa_text
from uuid import uuid4
from datetime import datetime
from .base import Base, UUID, DebVersion
from .core import LkModule


class SynchrotronIssueKind(enum.Enum):
    '''
    Kind of a Synchrotron issue.
    '''
    UNKNOWN        = 0
    NONE           = 1
    MERGE_REQUIRED = 2
    MAYBE_CRUFT    = 3
    SYNC_FAILED    = 4
    REMOVAL_FAILED = 5


class SynchrotronIssue(Base):
    '''
    Hints about why packages are not synchronized with a source distribution/suite.
    '''
    __tablename__ = 'synchrotron_issues'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    time_created = Column(DateTime(), default=datetime.utcnow) # Time when this excuse was created

    kind = Column(Enum(SynchrotronIssueKind)) # Kind of this issue, and usually also the reason for its existence.

    package_name = Column(String(256))  # Name of the source package that is to be synchronized

    source_suite  = Column(String(256))  # Source suite of this package, usually the one in Debian
    target_suite  = Column(String(256))  # Target suite of this package, from the target distribution

    source_version = Column(DebVersion()) # package version to be synced
    target_version = Column(DebVersion()) # version of the package in the target suite and repo, to be overriden

    details = Column(Text()) # additional information text about the issue (usually a log excerpt)


class SyncBlacklistEntry(Base):
    '''
    Synchrotron blacklist
    '''
    __tablename__ = 'synchrotron_blacklist'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    pkgname = Column(String(256))  # Name of the blacklisted package
    time_created = Column(DateTime(), default=datetime.utcnow) # Time when the package was blacklisted
    reason = Column(Text())  # Reason why the package is blacklisted

    user = Column(String(256))  # Person who marked this to be ignored


class SyncSourceSuite:
    '''
    Information about a distribution suite the we can sync data from
    '''
    name: str
    architectures = []
    components = []


class SyncSourceInfo:
    '''
    Information about a Synchrotron data source
    '''
    default_suite: str  # default suite name, e.g. "sid"
    suites: List[SyncSourceSuite]  # suites available in the source ("sid", "jessie", ...)

    repo_url: str  # URL of the package repository

    def __init_(self):
        self.suites = []


class SynchrotronConfig:
    '''
    Basic configuration for Synchrotron
    '''
    source_name: str    # Name of the source OS (usually "Debian")
    source: SyncSourceInfo

    sync_enabled: bool  # true if syncs should happen
    sync_binaries: bool # true if we should also sync binary packages

    def __init__(self):
        self.source = SyncSourceInfo()


def get_synchrotron_config():
    from .core import config_get_value

    d = config_get_value(LkModule.SYNCHROTRON, 'config')
    conf = SynchrotronConfig()
    conf.source_name = d.get('source_name')

    conf.sync_enabled = d.get('sync_enabled', False)
    conf.sync_binaries = d.get('sync_binaries', False)

    dsrc = d.get('source')
    if dsrc:
        conf.source.default_suite = dsrc.get('default_suite')
        conf.source.repo_url = dsrc.get('repo_url')

        for ds in dsrc.get('suites', []):
            suite = SyncSourceSuite()
            suite.name = ds.get('name')
            suite.architectures = ds.get('architectures', [])
            suite.components = ds.get('components', [])
            conf.source.suites.append(suite)


def set_synchrotron_config(conf):
    from .core import config_set_value

    d = {}
    d['source_name'] = conf.source_name

    d['sync_enabled'] = conf.sync_enabled
    d['sync_binaries'] = conf.sync_binaries

    dsrc = {}
    dsrc['default_suite'] = conf.source.default_suite
    dsrc['repo_url'] = conf.source.repo_url
    dsrc['suites'] = []

    for suite in conf.source.suites:
        ds = {}
        ds['name'] = suite.name
        ds['architectures'] = suite.architectures
        ds['components'] = suite.components

        dsrc['suites'].append(ds)

    d['source'] = dsrc

    config_set_value(LkModule.SYNCHROTRON, 'config', d)
