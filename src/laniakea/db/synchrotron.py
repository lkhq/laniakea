# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from uuid import uuid4
from datetime import UTC, datetime

from sqlalchemy import (
    Enum,
    Text,
    String,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, backref, relationship, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY

from .base import UUID, Base, DebVersion
from .archive import ArchiveSuite, ArchiveRepository


class SynchrotronSource(Base):
    """
    Definition of a foreign suite to sync packages from.
    """

    __tablename__ = 'synchrotron_sources'
    __table_args__ = (UniqueConstraint('os_name', 'suite_name', name='_os_suite_uc'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    os_name: Mapped[str] = mapped_column(Text, nullable=False)  # Name of the source OS (usually "Debian")
    suite_name: Mapped[str] = mapped_column(String(100), nullable=False)
    architectures: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    components: Mapped[list[str]] = mapped_column(ARRAY(String(100)))
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)


class SynchrotronConfig(Base):
    """
    Configuration for automatic synchrotron tasks.
    """

    __tablename__ = 'synchrotron_config'
    __table_args__ = (UniqueConstraint('repo_id', 'source_id', 'destination_suite_id', name='_repo_source_target_uc'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_repositories.id'), nullable=False)
    repo: Mapped[ArchiveRepository] = relationship('ArchiveRepository')

    source_id: Mapped[int] = mapped_column(Integer, ForeignKey('synchrotron_sources.id'), nullable=False)
    source: Mapped[SynchrotronSource] = relationship('SynchrotronSource')

    destination_suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=False)
    destination_suite: Mapped[ArchiveSuite] = relationship(
        'ArchiveSuite', backref=backref('synchrotron_configs', cascade='all, delete')
    )

    sync_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)  # true if syncs should happen
    sync_auto_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=False
    )  # true if syncs should happen automatically
    sync_binaries: Mapped[bool] = mapped_column(Boolean(), default=False)  # true if we should also sync binary packages
    auto_cruft_remove: Mapped[bool] = mapped_column(
        Boolean(), default=True
    )  # true if we should automatically try to remove cruft in target


class SyncBlacklistEntry(Base):
    """
    Synchrotron blacklist
    """

    __tablename__ = 'synchrotron_blacklist'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    config_id: Mapped[int] = mapped_column(Integer, ForeignKey('synchrotron_config.id'))
    config: Mapped['SynchrotronConfig'] = relationship(
        'SynchrotronConfig', backref=backref('blacklist_entries', cascade='all, delete')
    )

    pkgname: Mapped[str] = mapped_column(String(120))  # Name of the blacklisted package
    time_created: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )  # Time when the package was blacklisted
    reason: Mapped[str] = mapped_column(Text)  # Reason why the package is blacklisted

    user: Mapped[str] = mapped_column(String(200))  # Person who marked this to be ignored


class SynchrotronIssueKind(enum.IntEnum):
    """
    Kind of a Synchrotron issue.
    """

    UNKNOWN = 0
    NONE = 1
    MERGE_REQUIRED = 2
    MAYBE_CRUFT = 3
    SYNC_FAILED = 4
    REMOVAL_FAILED = 5

    def to_string(self):
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

    def __str__(self):
        return self.to_string()


class SynchrotronIssue(Base):
    """
    Hints about why packages are not synchronized with a source distribution/suite.
    """

    __tablename__ = 'synchrotron_issues'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    config_id: Mapped[int] = mapped_column(Integer, ForeignKey('synchrotron_config.id'), nullable=False)
    config: Mapped['SynchrotronConfig'] = relationship(
        'SynchrotronConfig', backref=backref('issues', cascade='all, delete')
    )

    time_created: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(UTC)
    )  # Time when this excuse was created

    kind: Mapped[SynchrotronIssueKind] = mapped_column(
        Enum(SynchrotronIssueKind)
    )  # Kind of this issue, and usually also the reason for its existence.

    package_name: Mapped[str] = mapped_column(String(200))  # Name of the source package that is to be synchronized

    source_suite: Mapped[str] = mapped_column(String(200))  # Source suite of this package, usually the one in Debian
    target_suite: Mapped[str] = mapped_column(String(200))  # Target suite of this package, from the target distribution

    source_version: Mapped[DebVersion] = mapped_column(DebVersion())  # package version to be synced
    target_version: Mapped[DebVersion] = mapped_column(
        DebVersion()
    )  # version of the package in the target suite and repo, to be overridden

    details: Mapped[str] = mapped_column(Text())  # additional information text about the issue (usually a log excerpt)
