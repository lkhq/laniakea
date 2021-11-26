# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import enum
from uuid import uuid4

from sqlalchemy import Enum, Text, Column, String, Boolean, Integer
from sqlalchemy.dialects.postgresql import ARRAY

from .base import UUID, Base


class ImageFormat(enum.IntEnum):
    '''
    Kind of the image to build.
    '''

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
    '''
    Instructions on how to do an automatic ISO image build.
    '''

    __tablename__ = 'image_build_recipes'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(Text(), nullable=False, unique=True)  # A unique name identifying this recipe

    format = Column(Enum(ImageFormat))  # The image format to build (e.g. ISO or IMG)
    distribution = Column(Text(), nullable=False)  # Name of the distribution, e.g. "Tanglu"
    suite = Column(Text(), nullable=False)  # Suite of the distribution to build an image for
    environment = Column(Text(), nullable=False)  # The environment (GNOME, Plasma, server, ...) to use
    style = Column(Text(), nullable=True)  # Style of the image (e.g. "oem" or "live")
    architectures = Column(ARRAY(String(128)))  # Architectures to build the image for
    # Architecture of the host that is allowed to build the images, or "any"
    host_architecture = Column(String(128), nullable=False)

    git_url = Column(Text(), nullable=False)  # Git repository URL with the live-build scripts / other build recipes
    result_move_to = Column(Text())  # Local or remote URL to copy the resulting build artifacts to
    # Number of images to retain, oldest images will be deleted first. -1 to keep images forever
    retain_images_n = Column(Integer(), default=-1)
    create_latest_symlink = Column(Boolean(), default=False)  # Create a "latest" symlink directory to the latest build
