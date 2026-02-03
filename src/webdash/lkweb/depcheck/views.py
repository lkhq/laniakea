# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import math
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass

from flask import Blueprint, abort, redirect, render_template

from laniakea.db import (
    PackageType,
    ArchiveSuite,
    DebcheckIssue,
    StatsEventKind,
    ArchiveRepoSuiteSettings,
    session_scope,
    make_stats_key,
)
from laniakea.archive import repo_suite_settings_for

from ..utils import is_uuid, fetch_statistics_for
from ..extensions import cache

depcheck = Blueprint('depcheck', __name__, url_prefix='/depcheck')


@dataclass
class RepoSuiteIssueOverview:
    rss: ArchiveRepoSuiteSettings
    src_issues_count: int = 0
    bin_issues_count: int = 0


@depcheck.route('/')
@cache.memoize(10 * 60)
def index():
    with session_scope() as session:
        repo_suites = (
            session.query(ArchiveRepoSuiteSettings)
            .join(ArchiveRepoSuiteSettings.suite)
            .filter(ArchiveRepoSuiteSettings.repo.has(is_debug=False))
            .order_by(ArchiveSuite.name.desc())
            .all()
        )

        rss_with_issues = []
        rss_good = []
        for rss in repo_suites:
            dci_src_count = (
                session.query(DebcheckIssue.uuid)
                .filter(
                    DebcheckIssue.package_type == PackageType.SOURCE,
                    DebcheckIssue.repo_id == rss.repo_id,
                    DebcheckIssue.suite_id == rss.suite_id,
                )
                .count()
            )
            dci_bin_count = (
                session.query(DebcheckIssue.uuid)
                .filter(
                    DebcheckIssue.package_type == PackageType.BINARY,
                    DebcheckIssue.repo_id == rss.repo_id,
                    DebcheckIssue.suite_id == rss.suite_id,
                )
                .count()
            )
            if dci_src_count != 0 or dci_bin_count != 0:
                rss_with_issues.append(RepoSuiteIssueOverview(rss, dci_src_count, dci_bin_count))
            else:
                rss_good.append(RepoSuiteIssueOverview(rss))

        return render_template(
            'depcheck/index.html', repo_suites_with_issues=rss_with_issues, repo_suites_good=rss_good
        )


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


@cache.memoize(30 * 60)
def fetch_depcheck_statistics_for(session, ptype: PackageType, repo_name: str, suite_name: str, arch_name: str) -> str:
    start_at = datetime.now(UTC) - timedelta(days=120)

    stat_key = make_stats_key(
        StatsEventKind.DEPCHECK_ISSUES_SRC if ptype == PackageType.SOURCE else StatsEventKind.DEPCHECK_ISSUES_BIN,
        repo_name,
        suite_name,
        arch_name,
    )
    return json.dumps(fetch_statistics_for(session, stat_key, start_at))


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

        if page <= 1:
            stats_raw = fetch_depcheck_statistics_for(session, package_type, repo_name, suite_name, arch_name)
        else:
            stats_raw = ''

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
            stats_raw=stats_raw,
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
