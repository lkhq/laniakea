# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

from flask import Blueprint, abort, render_template

from laniakea.db import SpearsExcuse, SpearsMigrationEntry, session_scope

from ..utils import is_uuid

migrations = Blueprint('migrations', __name__, url_prefix='/migrations')


@migrations.route('/')
def index():
    with session_scope() as session:
        entries = session.query(SpearsMigrationEntry).all()
        disp_entries = []
        for e in entries:
            disp_entries.append({'id': e.idname, 'from': ', '.join(e.source_suites), 'to': e.target_suite})

        return render_template('migrations/index.html', migrations=disp_entries)


@migrations.route('/excuses/<migration_id>/<int:page>')
def excuses_list(migration_id, page):
    with session_scope() as session:

        migration = session.query(SpearsMigrationEntry).filter(SpearsMigrationEntry.idname == migration_id).one()

        excuses_per_page = 50
        excuses_total = session.query(SpearsExcuse).filter(SpearsExcuse.migration_id == migration_id).count()
        page_count = math.ceil(excuses_total / excuses_per_page)

        excuses = (
            session.query(SpearsExcuse)
            .filter(SpearsExcuse.migration_id == migration_id)
            .order_by(SpearsExcuse.source_package)
            .slice((page - 1) * excuses_per_page, page * excuses_per_page)
            .all()
        )

        return render_template(
            'migrations/excuses.html',
            excuses=excuses,
            migration=migration,
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

        migration = {'idname': excuse.migration_id}
        return render_template('migrations/excuse.html', excuse=excuse, migration=migration)
