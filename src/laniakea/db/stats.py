# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


from enum import StrEnum
from datetime import datetime

from sqlalchemy import Text, Integer, DateTime, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .archive import ArchiveSuite, ArchiveRepository, ArchiveArchitecture


class StatsEventKind(StrEnum):
    """Kind of a recorded event for statistical purposes."""

    SRC_PKG_COUNT = 'sources'  # count of source packages
    BIN_PKG_COUNT = 'binaries'  # count of binary packages
    SOFTWARE_COMPONENTS = 'swcpts'  # count of software components (AppStream components)
    DEPCHECK_ISSUES_SRC = 'depcheck-issues-src'  # count of dependency check issues (source)
    DEPCHECK_ISSUES_BIN = 'depcheck-issues-bin'  # count of dependency check issues (binary)
    MIGRATIONS_PENDING = 'migrations-pending'  # pending package migrations
    JOB_QUEUE_DEPWAIT = 'job-queue-depwait'  # amount of packages waiting for build dependencies in the job queue
    JOB_QUEUE_PENDING = 'job-queue-pending'  # amount of eligible-to-build packages waiting in the job queue
    REVIEW_QUEUE_LENGTH = 'review-queue-length'  # amount of packages waiting in the review queue


def make_stats_key(
    kind: StatsEventKind,
    repo: ArchiveRepository | str,
    suite: ArchiveSuite | str | None,
    arch: ArchiveArchitecture | str | None = None,
) -> str:
    """Create a key to look up statistical entries."""

    repo_name = repo.name if isinstance(repo, ArchiveRepository) else repo
    suite_name = suite.name if isinstance(suite, ArchiveSuite) else suite
    arch_name = arch.name if isinstance(arch, ArchiveArchitecture) else arch

    if kind in (
        StatsEventKind.DEPCHECK_ISSUES_BIN,
        StatsEventKind.BIN_PKG_COUNT,
    ):
        if not arch_name:
            raise ValueError('Architecture must not be empty for stats event kind %s' % kind)
        if not suite_name:
            raise ValueError('Suite must not be empty for stats event kind %s' % kind)
        return '-'.join((kind, repo_name, suite_name, arch_name))
    elif kind in (StatsEventKind.SOFTWARE_COMPONENTS,):
        return '-'.join((kind, repo_name))
    elif kind in (StatsEventKind.JOB_QUEUE_DEPWAIT, StatsEventKind.JOB_QUEUE_PENDING):
        raise ValueError('Can not build statistics key for JobQueue statistics!')
    else:
        if not suite:
            raise ValueError('Suite must not be empty for stats event kind %s' % kind)
        return '-'.join((kind, repo_name, suite_name))


def make_stats_key_jobqueue(kind: StatsEventKind, arch_name: str) -> str:
    if kind not in (StatsEventKind.JOB_QUEUE_DEPWAIT, StatsEventKind.JOB_QUEUE_PENDING):
        raise ValueError('Can only build statistics key for JobQueue statistics!')
    return '-'.join((kind, arch_name))


class StatsEntry(Base):
    """
    Value of a certain archive property at a given time.
    """

    __tablename__ = 'statistics'

    key: Mapped[str] = mapped_column(Text, nullable=False)  # Unique identifier string for this event
    time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )  # Time when the value was measured

    value: Mapped[int] = mapped_column(Integer)  # Value at the given time

    __table_args__ = (PrimaryKeyConstraint('key', 'time'),)

    def __init__(self, key: str, value: int):
        self.key = key
        self.value = value
