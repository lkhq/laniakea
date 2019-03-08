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
from sqlalchemy import Column, Text, String, Integer, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy import text as sa_text
from uuid import uuid4
from datetime import datetime
from typing import List
from .base import Base, UUID, DebVersion
from .core import LkModule
from .archive import PackageType


class WorkerStatus(IntEnum):
    '''
    State this worker is in.
    '''
    UNKNOWN = 0
    ACTIVE = enum.auto()
    IDLE = enum.auto()
    MISSING = enum.auto()
    DEAD = enum.auto()


class SparkWorker(Base):
    '''
    An external machine/service that takes tasks from a Lighthouse server.
    '''

    __tablename__ = 'spark_workers'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    name = Column(Text())   # The machine/worker name
    owner = Column(Text())  # Owner of this worker

    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this worker was registered/created

    accepts = Column(ARRAY(Text()))  # Modules this worker will accept jobs for

    status = Column(Enum(WorkerStatus))  # Status/health of this machine
    enabled = Column(Boolean())  # Whether this worker should receive jobs or not

    last_ping = Column(DateTime())  # Time when we last got a message from the worker
    last_job = Column(UUID(as_uuid=True))  # The last job that was assigned to this worker
