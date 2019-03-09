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
import jsonpickle
from typing import List
from enum import Enum, IntEnum
from sqlalchemy import Column, Text, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy import text as sa_text
from uuid import uuid4
from datetime import datetime
from typing import List
from .base import Base, UUID, DebVersion
from .core import LkModule
from .archive import PackageType


class JobStatus(IntEnum):
    '''
    State of a job.
    '''
    UNKNOWN = 0
    WAITING = enum.auto()     # waiting for someone to take the job
    DEPWAIT = enum.auto()     # waiting for a dependency
    SCHEDULED = enum.auto()   # job has been assigned,
    RUNNING = enum.auto()     # the job is running
    DONE = enum.auto()        # the job is done
    TERMINATED = enum.auto()  # the job was terminated
    STARVING = enum.auto()    # the job was denied computing resources for an extended period of time


class JobResult(IntEnum):
    '''
    Result of a job.
    '''
    UNKNOWN = 0
    SUCCESS_PENDING = enum.auto()     # job was successful, but artifacts are still missing
    SUCCESS = enum.auto()             # job was successful
    FAILURE_DEPENDENCY = enum.auto()  # job was aborted because of a dependency issue
    FAILURE_PENDING = enum.auto()     # job failed, but artifacts or reports are still missing
    FAILURE = enum.auto()             # job failed


class JobKind(Enum):
    '''
    The different job kind identifier strings used by
    the different Laniakea modules which can enqueue jobs.
    '''
    OS_IMAGE_BUILD = 'os-image-build'
    PACKAGE_BUILD  = 'package-build'


class Job(Base):
    '''
    A task to be performed (e.g. by a Spark worker)
    '''

    __tablename__ = 'jobs'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    status = Column(Enum(JobStatus), default=JobStatus.WAITING)  # Status of this job

    module = Column(String(256))  # the name of the module responsible for this job
    kind = Column(String(256))  # kind of the job

    trigger = Column(UUID(as_uuid=True))  # ID of the entity responsible for triggering this job's creation

    version = Column(DebVersion())  # Version of the item this job is for (can be null)

    architecture = Column(Text(), default='any')  # Architecture this job can run on, "any" in case the architecture does not matter

    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this job was created.
    time_assigned = Column(DateTime())  # Time when this job was assigned to a worker.
    time_finished = Column(DateTime())  # Time when this job was finished.

    priority = Column(Integer())  # Priority of this job (higher value means faster execution of the task)

    worker = Column(UUID(as_uuid=True))  # Unique ID of the entity the job is assigned to

    architecture = Column(Text(), default='any')  # Architecture this job can run on, "any" in case the architecture does not matter

    result = Column(Enum(JobResult), default=JobResult.UNKNOWN)  # Result of this job

    data = Column(JSON)  # Job description data

    latest_log_excerpt = Column(Text())  # An excerpt of the current job log
