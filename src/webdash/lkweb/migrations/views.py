# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import math
from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template

from laniakea.db import (
    SpearsExcuse,
    SourcePackage,
    StatsEventKind,
    SpearsMigrationTask,
    session_scope,
    make_stats_key,
)

from ..utils import is_uuid, fetch_statistics_for
from ..extensions import cache

migrations = Blueprint('migrations', __name__, url_prefix='/migrations')


@migrations.route('/')
def index():
    with session_scope() as session:
        entries = session.query(SpearsMigrationTask).all()
        disp_entries = {}
        for e in entries:
            if e.repo.name not in disp_entries:
                disp_entries[e.repo.name] = []
            disp_entries[e.repo.name].append(
                {
                    'repo_name': e.repo.name,
                    'from': ', '.join([s.name for s in e.source_suites]),
                    'to': e.target_suite.name,
                }
            )

        return render_template('migrations/index.html', migrations=disp_entries)


@cache.memoize(30 * 60)
def fetch_excuses_statistics_for(session, repo_name: str, target_suite_name: str) -> str:
    start_at = datetime.utcnow() - timedelta(days=120)

    stat_key = make_stats_key(StatsEventKind.MIGRATIONS_PENDING, repo_name, target_suite_name)
    return json.dumps(fetch_statistics_for(session, stat_key, start_at))


@migrations.route('/excuses/<repo_name>/<target_suite_name>/<int:page>')
def excuses_list(repo_name, target_suite_name, page):
    with session_scope() as session:
        migration = (
            session.query(SpearsMigrationTask)
            .filter(
                SpearsMigrationTask.repo.has(name=repo_name),
                SpearsMigrationTask.target_suite.has(name=target_suite_name),
            )
            .one_or_none()
        )
        if not migration:
            abort(404)

        excuses_per_page = 50
        excuses_total = session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == migration.id).count()
        page_count = math.ceil(excuses_total / excuses_per_page)

        excuses = (
            session.query(SpearsExcuse)
            .join(SourcePackage)
            .filter(SpearsExcuse.migration_id == migration.id)
            .order_by(SourcePackage.name)
            .slice((page - 1) * excuses_per_page, page * excuses_per_page)
            .all()
        )

        if page <= 1:
            excuses_stats = fetch_excuses_statistics_for(session, migration.repo.name, migration.target_suite.name)
        else:
            excuses_stats = ''

        migration_source_suites_str = ', '.join([s.name for s in migration.source_suites])
        return render_template(
            'migrations/excuses.html',
            excuses=excuses,
            migration=migration,
            migration_source_suites_str=migration_source_suites_str,
            excuses_per_page=excuses_per_page,
            excuses_total=excuses_total,
            current_page=page,
            page_count=page_count,
            excuses_stats=excuses_stats,
        )


@migrations.route('/excuse/<uuid>')
def view_excuse(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        excuse = session.query(SpearsExcuse).filter(SpearsExcuse.uuid == uuid).one_or_none()
        if not excuse:
            abort(404)

        return render_template('migrations/excuse.html', excuse=excuse, migration=excuse.migration_task)
