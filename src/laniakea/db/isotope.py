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


class ImageKind(enum.IntEnum):
    '''
    Kind of the image to build.
    '''
    UNKNOWN = 0
    ISO = enum.auto()
    IMG = enum.auto()

    def __str__(self):
        v = self.value
        if v == ImageKind.ISO:
            return 'iso'
        elif v == ImageKind.IMG:
            return 'img'
        else:
            return 'unknown'


class ImageBuildRecipe(Base):
    '''
    Instructions on how to do an automatic ISO image build.
    '''

    __tablename__ = 'image_build_recipes'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    kind = Column(Enum(ImageKind))  # The kind of image to build

    name = Column(Text(), nullable=False, unique=True)  # A unique name identifying this recipe
    distribution = Column(Text())  # Name of the distribution, e.g. "Tanglu"
    suite = Column(Text())  # Suite of the distribution to build an image for
    flavor = Column(Text())  # The flavor to build
    architectures = Column(ARRAY(String(128)))  # Architectures to build the image for

    git_url = Column(Text())  # Git repository URL with the live-build scripts / other build recipes
    result_move_to = Column(Text())  # Local or remote URL to copy the resulting build artifacts to

    def regenerate_name(self):
        self.name = '{}:{}-{}-{}'.format(str(self.kind),
                                         self.distribution,
                                         self.suite,
                                         self.flavor).lower()
