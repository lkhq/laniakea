# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, render_template
from laniakea.db import session_scope, ArchiveSuite, SynchrotronConfig, SynchrotronIssue, \
    SynchrotronIssueKind, SyncBlacklistEntry

synchronization = Blueprint('synchronization',
                            __name__,
                            url_prefix='/sync')


@synchronization.route('/')
def index():
    with session_scope() as session:
        sync_configs = session.query(SynchrotronConfig) \
            .join(SynchrotronConfig.destination_suite) \
            .order_by(ArchiveSuite.name).all()

        return render_template('synchronization/index.html', sync_configs=sync_configs)


@synchronization.route('/<suite_name>')
def issues_table(suite_name):
    with session_scope() as session:
        issues = session.query(SynchrotronIssue) \
            .filter(SynchrotronIssue.target_suite == suite_name) \
            .all()

        return render_template('synchronization/sync_issue_table.html',
                               issues=issues,
                               SyncIssueKind=SynchrotronIssueKind,
                               target_suite_name=suite_name)


@synchronization.route('/blacklist')
def blacklist():
    with session_scope() as session:
        entries = session.query(SyncBlacklistEntry).all()

        return render_template('synchronization/blacklist.html', entries=entries)
