# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import uuid
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Enum, Text, Index, Column, String, Integer, DateTime, ForeignKey
from marshmallow import EXCLUDE, Schema, fields
from sqlalchemy.orm import backref, relationship
from sqlalchemy.dialects.postgresql import JSON, ARRAY

from .base import UUID, Base, DebVersion
from .archive import PackageType, ArchiveSuite, ArchiveRepository

# UUID namespace for uuid5 IDs for Debcheck entities
DEBCHECK_ENTITY_UUID = uuid.UUID('43f7d768-7cce-4bd7-90ce-1ea6dec23a60')


class PackageIssue(Schema):
    '''
    Information about the package issue reason.
    '''

    package_type = fields.Enum(PackageType, by_value=True)
    package_name = fields.Str()
    package_version = fields.Str()
    architectures = fields.List(fields.Str())

    depends = fields.Str(allow_none=True)
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

    # Architectures this issue affects, may be a wildcard like "any" or (list of) architecture expressions
    architectures = Column(ARRAY(Text()), default=['any'])

    package_name = Column(String(200))  # Name of the package this issue affects
    package_version = Column(DebVersion())  # Version of the package this issue affects

    _missing_json = Column('missing', JSON)  # information about missing packages
    _conflicts_json = Column('conflicts', JSON)  # information about conflicts

    _missing = None
    _conflicts = None

    @staticmethod
    def generate_uuid(issue, repo: ArchiveRepository | None, suite: ArchiveSuite | None):
        """Issue entities have a UUID based on a set of data, this function generates the UUID."""
        if not repo:
            repo = issue.repo
        if not suite:
            suite = issue.suite
        return uuid.uuid5(
            DEBCHECK_ENTITY_UUID,
            '{}:{}:{}:{}/{} [{}]'.format(
                repo.id,
                suite.id,
                issue.package_type.value,
                issue.package_name,
                issue.package_version,
                ','.join(issue.architectures),
            ),
        )

    def update_uuid(self, repo: ArchiveRepository | None = None, suite: ArchiveSuite | None = None):
        self.uuid = DebcheckIssue.generate_uuid(self, repo, suite)

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


idx_debcheck_issues_repo = Index(
    'idx_debcheck_issues_repo',
    DebcheckIssue.repo_id,
)

idx_debcheck_issues_repo_suite_type = Index(
    'idx_debcheck_issues_repo_suite_type', DebcheckIssue.package_type, DebcheckIssue.repo_id, DebcheckIssue.suite_id
)
