# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2024 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from enum import IntEnum
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Enum, Text, Index, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.dialects.postgresql import JSON

from .base import UUID, Base, DebVersion
from .archive import ArchiveSuite


class JobStatus(IntEnum):
    '''
    State of a job.
    '''

    UNKNOWN = 0
    WAITING = enum.auto()  # waiting for someone to take the job
    DEPWAIT = enum.auto()  # waiting for a dependency
    SCHEDULED = enum.auto()  # job has been assigned,
    RUNNING = enum.auto()  # the job is running
    DONE = enum.auto()  # the job is done
    TERMINATED = enum.auto()  # the job was terminated
    STARVING = enum.auto()  # the job was denied computing resources for an extended period of time


class JobResult(IntEnum):
    '''
    Result of a job.
    '''

    UNKNOWN = 0
    SUCCESS_PENDING = enum.auto()  # job was successful, but artifacts are still missing
    SUCCESS = enum.auto()  # job was successful
    FAILURE_DEPENDENCY = enum.auto()  # job was aborted because of a dependency issue
    FAILURE_PENDING = enum.auto()  # job failed, but artifacts or reports are still missing
    FAILURE = enum.auto()  # job failed

    def __str__(self):
        if self.value == self.SUCCESS_PENDING:
            return 'success-pending'
        if self.value == self.SUCCESS:
            return 'success'
        if self.value == self.FAILURE_DEPENDENCY:
            return 'failure-dependency'
        if self.value == self.FAILURE_PENDING:
            return 'failure-pending'
        if self.value == self.FAILURE:
            return 'failure'
        return 'JobResult.' + str(self.name)


class JobKind:
    '''
    The different job kind identifier strings used by
    the different Laniakea modules which can enqueue jobs.
    '''

    OS_IMAGE_BUILD = 'os-image-build'
    PACKAGE_BUILD = 'package-build'


class Job(Base):
    """
    A task to be performed (e.g. by a Spark worker)
    """

    __tablename__ = 'jobs'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.WAITING)  # Status of this job

    module: Mapped[str] = mapped_column(String(100), nullable=False)  # the name of the module responsible for this job
    kind: Mapped[str] = mapped_column(String(200), nullable=False)  # kind of the job

    trigger: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # ID of the entity responsible for triggering this job's creation

    suite_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_suites.id'), nullable=True)
    suite: Mapped[ArchiveSuite] = relationship('ArchiveSuite')  # Suite this job is supposed to run on (can be null)
    version: Mapped[DebVersion] = mapped_column(
        DebVersion(), nullable=True
    )  # Version of the item this job is for (can be null)

    # Architecture this job can run on, "any" in case the architecture does not matter
    architecture: Mapped[str] = mapped_column(String(80), default='any')

    time_created: Mapped[datetime] = mapped_column(
        DateTime(), default=datetime.utcnow
    )  # Time when this job was created.
    time_assigned: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True
    )  # Time when this job was assigned to a worker.
    time_finished: Mapped[datetime] = mapped_column(DateTime(), nullable=True)  # Time when this job was finished.

    priority: Mapped[int] = mapped_column(
        Integer(), default=0
    )  # Priority of this job (higher value means faster execution of the task)

    worker: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # Unique ID of the entity the job is assigned to

    result: Mapped[JobResult] = mapped_column(Enum(JobResult), default=JobResult.UNKNOWN)  # Result of this job

    data: Mapped[dict] = mapped_column(JSON, default={})  # Job-specific payload data

    latest_log_excerpt: Mapped[str] = mapped_column(Text(), nullable=True)  # An excerpt of the current job log

    def is_taken(self):
        return self.status == JobStatus.SCHEDULED or self.status == JobStatus.RUNNING

    def has_result(self):
        return self.result != JobResult.UNKNOWN

    def is_failed(self):
        return (
            self.result == JobResult.FAILURE
            or self.result == JobResult.FAILURE_PENDING
            or self.result == JobResult.FAILURE_DEPENDENCY
        )


idx_jobs_status = Index(
    'idx_jobs_status',
    Job.status,
)

idx_jobs_status_result_trigger_ver_arch = Index(
    'idx_jobs_status_result_trigger_ver_arch',
    Job.status,
    Job.result,
    Job.trigger,
    Job.version,
    Job.architecture,
)
