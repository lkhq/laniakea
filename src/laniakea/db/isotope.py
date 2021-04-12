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
from sqlalchemy import Column, Text, String, Enum, Integer, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from uuid import uuid4
from .base import Base, UUID


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
    host_architecture = Column(String(128), nullable=False)  # Architecture of the host that is allowed to build the images, or "any"

    git_url = Column(Text(), nullable=False)  # Git repository URL with the live-build scripts / other build recipes
    result_move_to = Column(Text())  # Local or remote URL to copy the resulting build artifacts to
    retain_images_n = Column(Integer(), default=-1)  # Number of images to retain, oldest images will be deleted first. -1 to keep images forever
    create_latest_symlink = Column(Boolean(), default=False)  # Create a "latest" symlink directory to the latest build
