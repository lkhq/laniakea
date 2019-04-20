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

import jsonpickle
from typing import List
from sqlalchemy import Column, Text, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from uuid import uuid4
from datetime import datetime
from .base import Base, UUID, DebVersion
from .archive import PackageType


class PackageIssue:
    '''
    Information about the package issue reason.
    '''
    package_type: PackageType
    package_name: str
    package_version: str
    architecture: str

    depends: str
    unsat_dependency: str
    unsat_conflict: str


class PackageConflict:
    '''
    Information about a conflict between packages.
    '''

    pkg1: PackageIssue
    pkg2: PackageIssue

    depchain1: List[PackageIssue]
    depchain2: List[PackageIssue]


class DebcheckIssue(Base):
    '''
    Data for a package migration excuse, as emitted by Britney
    '''

    __tablename__ = 'debcheck_issues'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    time = Column(DateTime(), default=datetime.utcnow)  # Time when this excuse was created

    package_type = Column(Enum(PackageType))

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    suite = relationship('ArchiveSuite')

    architecture = Column(Text(), default='any')  # Architecture this issue affects, may be a wildcard like "any" or architecture expression

    package_name = Column(String(256))  # Name of the package this issue affects
    package_version = Column(DebVersion())  # Version of the package this issue affects

    missing = Column(JSON)  # information about missing packages
    conflicts = Column(JSON)  # information about conflicts

    def get_issues_missing(self):
        if not self.missing:
            return None
        return jsonpickle.decode(self.missing)

    def set_issues_missing(self, v):
        self.missing = jsonpickle.encode(v)

    def get_issues_conflicts(self):
        if not self.conflicts:
            return None
        return jsonpickle.decode(self.conflicts)

    def set_issues_conflicts(self, v):
        self.conflicts = jsonpickle.encode(v)
