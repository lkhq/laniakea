# Copyright (C) 2019-2020 Matthias Klumpp <matthias@tenstral.net>
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
from sqlalchemy import Column, Text, String, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA
from sqlalchemy.orm import relationship
from uuid import uuid4
from .base import Base, UUID, DebVersion


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
