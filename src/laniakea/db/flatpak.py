# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from uuid import uuid4

from sqlalchemy import Enum, Text, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA

from .base import UUID, Base, DebVersion
from .archive import ArchiveArchitecture


class FlatpakRepository(Base):
    """
    A Flatpak repository.
    """

    __tablename__ = 'flatpak_repositories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100), unique=True
    )  # Machine-readable name of the repository (used in directory paths)
    collection_id: Mapped[str] = mapped_column(Text(), unique=True)  # Collection-ID of this repository

    title: Mapped[str] = mapped_column(Text())
    comment: Mapped[str] = mapped_column(Text())
    description: Mapped[str] = mapped_column(Text())

    url_homepage: Mapped[str] = mapped_column(Text())
    url_icon: Mapped[str] = mapped_column(Text())

    default_branch: Mapped[str] = mapped_column(String(100), default='stable')
    gpg_key_id: Mapped[str] = mapped_column(Text())  # ID of the GPG key used for signing this repository

    allowed_branches: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=['stable']
    )  # List of allowed branch names

    def __init__(self, name: str):
        self.name = name


class FlatpakRefKind(enum.Enum):
    '''
    Kind of a Flatpak Ref.
    '''

    UNKNOWN = enum.auto()
    APP = enum.auto()
    RUNTIME = enum.auto()

    def to_string(self):
        if self.value == self.APP.value:
            return 'app'
        elif self.value == self.RUNTIME.value:
            return 'runtime'
        return 'unknown'

    def __str__(self):
        return self.to_string()


class FlatpakRef(Base):
    """
    Flatpak object/app/runtime reference.
    """

    __tablename__ = 'flatpak_refs'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey('flatpak_repositories.id'))
    repo: Mapped['FlatpakRepository'] = relationship('FlatpakRepository')

    kind: Mapped[FlatpakRefKind] = mapped_column(Enum(FlatpakRefKind))
    name: Mapped[str] = mapped_column(Text())
    version: Mapped[DebVersion] = mapped_column(DebVersion())  # Version of this Ref

    branch: Mapped[str] = mapped_column(String(100), default='stable')
    commit: Mapped[bytes] = mapped_column(BYTEA())  # OSTree commit ID of this ref

    architecture_id: Mapped[int] = mapped_column(Integer, ForeignKey('archive_architectures.id'))
    architecture: Mapped[ArchiveArchitecture] = relationship(
        'ArchiveArchitecture'
    )  # Architecture this reference was made for

    # TODO: runtime
    # TODO: sdk
