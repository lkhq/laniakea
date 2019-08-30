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

import json
from sqlalchemy import Column, Text, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from marshmallow import Schema, fields, EXCLUDE
from uuid import uuid4
from datetime import datetime
from .base import Base, UUID, DebVersion
from .archive import PackageType


class PackageIssue(Schema):
    '''
    Information about the package issue reason.
    '''
    package_type = fields.Int()  # PackageType enum
    package_name = fields.Str()
    package_version = fields.Str()
    architecture = fields.Str()

    depends = fields.Str()
    unsat_dependency = fields.Str()
    unsat_conflict = fields.Str()

    class Meta:
        unknown = EXCLUDE


class PackageConflict(Schema):
    '''
    Information about a conflict between packages.
    '''

    pkg1 = fields.Nested(PackageIssue())
    pkg2 = fields.Nested(PackageIssue())

    depchain1 = fields.List(fields.Nested(PackageIssue()))
    depchain2 = fields.List(fields.Nested(PackageIssue()))

    class Meta:
        unknown = EXCLUDE


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

    suite_id = Column(Integer, ForeignKey('archive_suites.id', ondelete='cascade'))
    suite = relationship('ArchiveSuite', backref=backref('debcheck_issues', passive_deletes=True))

    architectures = Column(ARRAY(Text()), default=['any'])  # Architectures this issue affects, may be a wildcard like "any" or (list of) architecture expressions

    package_name = Column(String(256))  # Name of the package this issue affects
    package_version = Column(DebVersion())  # Version of the package this issue affects

    _missing_json = Column('missing', JSON)  # information about missing packages
    _conflicts_json = Column('conflicts', JSON)  # information about conflicts

    _missing = None
    _conflicts = None

    @property
    def missing(self):
        if self._missing is not None:
            return self._missing
        if not self._missing_json:
            return []
        jlist = json.loads(self._missing_json)
        schema = PackageIssue()
        self._missing = [schema.load(d) for d in jlist]
        return self._missing

    @missing.setter
    def missing(self, v):
        self._missing = None
        schema = PackageIssue()
        self._missing_json = json.dumps([schema.dump(e) for e in v])

    @property
    def conflicts(self):
        if self._conflicts is not None:
            return self._conflicts
        if not self._conflicts_json:
            return []
        jlist = json.loads(self._conflicts_json)
        schema = PackageConflict()
        self._conflicts = [schema.load(d) for d in jlist]
        return self._conflicts

    @conflicts.setter
    def conflicts(self, v):
        self._conflicts = None
        schema = PackageConflict()
        self._conflicts_json = json.dumps([schema.dump(e) for e in v])
