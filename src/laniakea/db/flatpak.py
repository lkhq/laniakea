# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from uuid import uuid4

from sqlalchemy import Enum, Text, Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA

from .base import UUID, Base, DebVersion


class FlatpakRepository(Base):
    '''
    A Flatpak repository.
    '''

    __tablename__ = 'flatpak_repositories'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Machine-readable name of the repository (used in directory paths)
    collection_id = Column(Text(), unique=True)  # Collection-ID of this repository

    title = Column(Text())
    comment = Column(Text())
    description = Column(Text())

    url_homepage = Column(Text())
    url_icon = Column(Text())

    default_branch = Column(String(128), default='stable')
    gpg_key_id = Column(Text())  # ID of the GPG key used for signing this repository

    allowed_branches = Column(ARRAY(String(128)))  # List of allowed branch names

    def __init__(self, name):
        self.name = name


class FlatpakRefKind(enum.IntEnum):
    '''
    Kind of a Flatpak Ref.
    '''

    UNKNOWN = enum.auto()
    APP = enum.auto()
    RUNTIME = enum.auto()

    def __str__(self):
        if self.value == self.APP:
            return 'app'
        elif self.value == self.RUNTIME:
            return 'runtime'
        return 'unknown'


class FlatpakRef(Base):
    '''
    Flatpak object/app/runtime reference.
    '''

    __tablename__ = 'flatpak_refs'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    repo_id = Column(Integer, ForeignKey('flatpak_repositories.id'))
    repo = relationship('FlatpakRepository')

    kind = Column(Enum(FlatpakRefKind))
    name = Column(Text())
    version = Column(DebVersion())  # Version of this Ref

    branch = Column(String(128), default='stable')
    commit = Column(BYTEA())  # OSTree commit ID of this ref

    architecture_id = Column(Integer, ForeignKey('archive_architectures.id'))
    architecture = relationship('ArchiveArchitecture')  # Architecture this reference was made for

    # TODO: runtime
    # TODO: sdk
