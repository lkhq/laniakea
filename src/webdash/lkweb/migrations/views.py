# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

from flask import Blueprint, abort, render_template

from laniakea.db import SpearsExcuse, SourcePackage, SpearsMigrationTask, session_scope

from ..utils import is_uuid

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
