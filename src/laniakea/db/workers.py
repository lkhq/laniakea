# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from enum import IntEnum
from uuid import uuid4
from datetime import UTC, datetime

from sqlalchemy import Enum, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON, ARRAY

from .base import UUID, Base


class WorkerStatus(IntEnum):
    """
    State this worker is in.
    """

    UNKNOWN = 0
    ACTIVE = enum.auto()
    IDLE = enum.auto()
    MISSING = enum.auto()
    DEAD = enum.auto()


class SparkWorker(Base):
    """
    An external machine/service that takes tasks from a Lighthouse server.
    """

    __tablename__ = 'spark_workers'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(Text())  # The machine/worker name
    owner: Mapped[str] = mapped_column(Text(), nullable=True)  # Owner of this worker

    time_created: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(UTC)
    )  # Time when this worker was registered/created

    accepts: Mapped[list[str]] = mapped_column(ARRAY(Text()), default=[])  # Modules this worker will accept jobs for
    architectures: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), default=[]
    )  # Architectures this worker will accept jobs for

    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus), default=WorkerStatus.UNKNOWN
    )  # Status/health of this machine
    enabled: Mapped[bool] = mapped_column(Boolean(), default=False)  # Whether this worker should receive jobs or not

    last_ping: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: datetime.now(UTC)
    )  # Time when we last got a message from the worker

    data: Mapped[dict] = mapped_column(JSON, default={})  # Custom worker properties
