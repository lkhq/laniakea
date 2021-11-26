# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from enum import IntEnum
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Enum, Text, Column, Boolean, DateTime
from sqlalchemy.dialects.postgresql import ARRAY

from .base import UUID, Base


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

    name = Column(Text())  # The machine/worker name
    owner = Column(Text())  # Owner of this worker

    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this worker was registered/created

    accepts = Column(ARRAY(Text()))  # Modules this worker will accept jobs for

    status = Column(Enum(WorkerStatus))  # Status/health of this machine
    enabled = Column(Boolean())  # Whether this worker should receive jobs or not

    last_ping = Column(DateTime())  # Time when we last got a message from the worker
    last_job = Column(UUID(as_uuid=True))  # The last job that was assigned to this worker
