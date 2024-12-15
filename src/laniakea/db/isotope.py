# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from uuid import uuid4

from sqlalchemy import Enum, Text, String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY

from .base import UUID, Base


class ImageFormat(enum.IntEnum):
    """
    Kind of the image to build.
    """

    UNKNOWN = 0
    ISO = enum.auto()
    IMG = enum.auto()

    def __str__(self):
        if self.value == self.ISO:
            return 'iso'
        if self.value == self.IMG:
            return 'img'
        return 'ImageFormat.' + str(self.name)


class ImageBuildRecipe(Base):
    """
    Instructions on how to do an automatic ISO image build.
    """

    __tablename__ = 'image_build_recipes'

    uuid: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)  # A unique name identifying this recipe

    format: Mapped[ImageFormat] = mapped_column(Enum(ImageFormat))  # The image format to build (e.g. ISO or IMG)
    distribution: Mapped[str] = mapped_column(Text(), nullable=False)  # Name of the distribution, e.g. "Tanglu"
    suite: Mapped[str] = mapped_column(Text(), nullable=False)  # Suite of the distribution to build an image for
    environment: Mapped[str] = mapped_column(
        Text(), nullable=False
    )  # The environment (GNOME, Plasma, server, ...) to use
    style: Mapped[str] = mapped_column(Text(), nullable=True)  # Style of the image (e.g. "oem" or "live")
    architectures: Mapped[list[str]] = mapped_column(
        ARRAY(String(80)), default=[]
    )  # Architectures to build the image for
    # Architecture of the host that is allowed to build the images, or "any"
    host_architecture: Mapped[str] = mapped_column(String(80), nullable=False)

    git_url: Mapped[str] = mapped_column(
        Text(), nullable=False
    )  # Git repository URL with the live-build scripts / other build recipes
    result_move_to: Mapped[str] = mapped_column(Text())  # Local or remote URL to copy the resulting build artifacts to
    # Number of images to retain, oldest images will be deleted first. -1 to keep images forever
    retain_images_n: Mapped[int] = mapped_column(Integer(), default=-1)
    create_latest_symlink: Mapped[bool] = mapped_column(
        Boolean(), default=False
    )  # Create a "latest" symlink directory to the latest build
