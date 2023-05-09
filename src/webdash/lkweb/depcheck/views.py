# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

from flask import Blueprint, abort, redirect, render_template

from laniakea.db import (
    PackageType,
    ArchiveSuite,
    DebcheckIssue,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import repo_suite_settings_for

from ..utils import is_uuid

depcheck = Blueprint('depcheck', __name__, url_prefix='/depcheck')


@depcheck.route('/')
def index():
    with session_scope() as session:
        repo_suites = (
            session.query(ArchiveRepoSuiteSettings)
            .join(ArchiveRepoSuiteSettings.suite)
            .filter(ArchiveRepoSuiteSettings.repo.has(is_debug=False))
            .order_by(ArchiveSuite.name.desc())
            .all()
        )

        return render_template('depcheck/index.html', repo_suites=repo_suites)


@depcheck.route('/<repo_name>/<suite_name>/<ptype>/')
@depcheck.route('/<repo_name>/<suite_name>/<ptype>')
def issue_list_shortcut(repo_name, suite_name, ptype):
    """Convenience redirect to the full issue list page."""
    with session_scope() as session:
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one_or_none()
        if not suite:
            abort(404)

        return redirect(
            '/depcheck/{}/{}/{}/{}/1'.format(repo_name, suite_name, ptype, suite.primary_architecture.name), code=302
        )


@depcheck.route('/<repo_name>/<suite_name>/<ptype>/<arch_name>/<int:page>')
def issue_list(repo_name, suite_name, ptype, arch_name, page):
    if ptype == 'binary':
        package_type = PackageType.BINARY
    else:
        package_type = PackageType.SOURCE

    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
        if not rss:
            abort(404)

        issues_per_page = 50
        issues_total = (
            session.query(DebcheckIssue)
            .filter(DebcheckIssue.package_type == package_type)
            .filter(DebcheckIssue.repo_id == rss.repo.id)
            .filter(DebcheckIssue.suite_id == rss.suite.id)
            .filter(DebcheckIssue.architectures.any(arch_name))
            .count()
        )
        page_count = math.ceil(issues_total / issues_per_page)

        issues = (
            session.query(DebcheckIssue)
            .filter(DebcheckIssue.package_type == package_type)
            .filter(DebcheckIssue.repo_id == rss.repo.id)
            .filter(DebcheckIssue.suite_id == rss.suite.id)
            .filter(DebcheckIssue.architectures.any(arch_name))
            .order_by(DebcheckIssue.package_name)
            .slice((page - 1) * issues_per_page, page * issues_per_page)
            .all()
        )

        return render_template(
            'depcheck/issues_list.html',
            ptype=ptype,
            issues=issues,
            rss=rss,
            arch_name=arch_name,
            issues_per_page=issues_per_page,
            issues_total=issues_total,
            current_page=page,
            page_count=page_count,
        )


@depcheck.route('/<repo_name>/<suite_name>/issue/<uuid>')
def issue_details(repo_name, suite_name, uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
        if not rss:
            abort(404)

        issue = (
            session.query(DebcheckIssue)
            .filter(DebcheckIssue.repo_id == rss.repo.id)
            .filter(DebcheckIssue.suite_id == rss.suite.id)
            .filter(DebcheckIssue.uuid == uuid)
            .one_or_none()
        )
        if not issue:
            abort(404)

        # cache information (as it has to be decoded from json)
        missing = issue.missing
        conflicts = issue.conflicts
        ptype = 'source' if issue.package_type == PackageType.SOURCE else 'binary'

        return render_template(
            'depcheck/issue.html',
            PackageType=PackageType,
            ptype=ptype,
            issue=issue,
            arch_name=', '.join(issue.architectures),
            rss=rss,
            missing=missing,
            conflicts=conflicts,
        )
