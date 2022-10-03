# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from dataclasses import dataclass

from flask import Blueprint, render_template

import laniakea.typing as T
from laniakea.db import (
    ArchiveSuite,
    SourcePackage,
    ArchiveRepository,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
    session_scope,
)

from ..utils import humanized_timediff

review_queues = Blueprint('review_queues', __name__, url_prefix='/review')


@dataclass
class NewQueueEntryData:
    info: ArchiveQueueNewEntry
    url: str
    spkg: SourcePackage


@dataclass
class NewQueueData:
    rss: ArchiveRepoSuiteSettings
    entries: T.List[NewQueueEntryData]


@review_queues.route('/')
def index():
    with session_scope() as session:
        repo_suites = (
            session.query(ArchiveRepoSuiteSettings)
            .join(ArchiveRepository, ArchiveSuite)
            .filter(ArchiveRepoSuiteSettings.auto_overrides.is_(False))
            .filter(ArchiveRepoSuiteSettings.accept_uploads.is_(True))
            .order_by(ArchiveRepository.name, ArchiveSuite.name)
            .all()
        )

        new_queues: T.List[NewQueueData] = []
        for rss in repo_suites:
            queue_entries = (
                session.query(ArchiveQueueNewEntry)
                .filter(
                    ArchiveQueueNewEntry.destination_id == rss.suite_id,
                    ArchiveQueueNewEntry.package.has(repo_id=rss.repo_id),
                )
                .all()
            )

            qdata = NewQueueData(rss, [])
            for entry in queue_entries:
                spkg = entry.package

                qedata = NewQueueEntryData(entry, '#', spkg)
                qedata.url = (
                    rss.repo.get_new_queue_url()
                    + '/'
                    + spkg.directory
                    + '/'
                    + '{}_{}.changes'.format(spkg.name, spkg.version)
                )
                qdata.entries.append(qedata)
            new_queues.append(qdata)

        return render_template('review_queues/index.html', new_queues=new_queues, humanized_timediff=humanized_timediff)
