# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from datetime import UTC, datetime

from laniakea.db import (
    ArchiveSuite,
    SourcePackage,
    ChangesUrgency,
    ArchiveComponent,
    ArchiveRepository,
    SpearsMigrationTask,
    session_scope,
)
from spears.spearsengine import SpearsEngine


def _add_source_package(
    session,
    repo: ArchiveRepository,
    name: str,
    version: str,
    urgency: ChangesUrgency,
    suites: list[ArchiveSuite],
    *,
    deleted: bool = False,
) -> SourcePackage:
    """Register a bare-bones source package with the database, without any files."""

    spkg = SourcePackage(name, version, repo)
    spkg.component = session.query(ArchiveComponent).filter(ArchiveComponent.name == 'main').one()
    spkg.architectures = ['any']
    spkg.format_version = '3.0 (quilt)'
    spkg.maintainer = 'A Maintainer <maint@example.com>'
    spkg.directory = 'pool/main/{}/{}'.format(name[0], name)
    spkg.expected_binaries = []
    spkg.changes_urgency = urgency
    spkg.suites = suites
    if deleted:
        spkg.time_deleted = datetime.now(UTC)
    session.add(spkg)

    return spkg


def test_collect_urgencies(database, tmp_path):
    """
    Britney only honors urgencies of versions that are newer than the one in the target suite, and not
    newer than the one in the source suite. So the urgencies file has to list the source suite's packages,
    or everything just ends up with the default urgency (#32).
    """

    with session_scope() as session:
        master = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'master').one()
        extra = session.query(ArchiveRepository).filter(ArchiveRepository.name == 'extra').one()
        unstable = session.query(ArchiveSuite).filter(ArchiveSuite.name == 'unstable').one()
        stable = session.query(ArchiveSuite).filter(ArchiveSuite.name == 'stable').one()

        # an old version has migrated already, the new one is waiting in unstable
        _add_source_package(session, master, 'alpha', '1.0-1', ChangesUrgency.LOW, [stable])
        _add_source_package(session, master, 'alpha', '1.0-3', ChangesUrgency.LOW, [unstable])
        # critical upload that was superseded and expired from unstable before it could migrate,
        # its urgency must still be considered
        _add_source_package(session, master, 'alpha', '1.0-2', ChangesUrgency.CRITICAL, [], deleted=True)

        # entirely new package that only exists in the source suite
        _add_source_package(session, master, 'beta', '0.5-1', ChangesUrgency.HIGH, [unstable])

        # package that only exists in the target suite, there is nothing to migrate
        _add_source_package(session, master, 'gamma', '2.0-1', ChangesUrgency.MEDIUM, [stable])

        # packages from other repositories must not leak into the list
        _add_source_package(session, extra, 'alpha', '9.0-1', ChangesUrgency.EMERGENCY, [unstable])
        _add_source_package(session, extra, 'delta', '1.0-1', ChangesUrgency.HIGH, [unstable])

        mtask = SpearsMigrationTask()
        mtask.repo = master
        mtask.source_suites = [unstable]
        mtask.target_suite = stable
        mtask.delays = {}
        session.add(mtask)
        session.flush()

        os.makedirs(tmp_path / 'state')
        engine = SpearsEngine()
        engine._collect_urgencies(session, tmp_path, mtask)

    with open(tmp_path / 'state' / 'age-policy-urgencies', 'r', encoding='utf-8') as f:
        lines = sorted(line.strip() for line in f if line.strip())

    assert lines == [
        'alpha 1.0-1 low',
        'alpha 1.0-2 critical',
        'alpha 1.0-3 low',
        'beta 0.5-1 high',
    ]
