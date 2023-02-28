# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, abort, render_template

from laniakea.db import (
    ArchiveSuite,
    SynchrotronIssue,
    SynchrotronConfig,
    SyncBlacklistEntry,
    SynchrotronIssueKind,
    session_scope,
)

synchronization = Blueprint('synchronization', __name__, url_prefix='/sync')


@synchronization.route('/')
def index():
    with session_scope() as session:
        sync_configs = (
            session.query(SynchrotronConfig).join(SynchrotronConfig.destination_suite).order_by(ArchiveSuite.name).all()
        )

        return render_template('synchronization/index.html', sync_configs=sync_configs)


@synchronization.route('<int:config_id>/issues')
def issues_table(config_id: int):
    with session_scope() as session:
        sync_config = session.query(SynchrotronConfig).filter(SynchrotronConfig.id == config_id).one_or_none()
        if not sync_config:
            abort(404)
        issues = session.query(SynchrotronIssue).filter(SynchrotronIssue.config_id == sync_config.id).all()

        return render_template(
            'synchronization/sync_issue_table.html',
            issues=issues,
            SyncIssueKind=SynchrotronIssueKind,
            sconf=sync_config,
        )


@synchronization.route('<int:config_id>/blacklist/')
def blacklist(config_id: int):
    with session_scope() as session:
        sync_config = session.query(SynchrotronConfig).filter(SynchrotronConfig.id == config_id).one_or_none()
        if not sync_config:
            abort(404)
        entries = session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.config_id == sync_config.id).all()

        return render_template('synchronization/blacklist.html', entries=entries, sconf=sync_config)
