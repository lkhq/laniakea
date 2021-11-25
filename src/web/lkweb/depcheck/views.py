# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

from flask import Blueprint, abort, render_template

from laniakea.db import ArchiveSuite, DebcheckIssue, PackageType, session_scope

from ..utils import is_uuid

depcheck = Blueprint('depcheck',
                     __name__,
                     url_prefix='/depcheck')


@depcheck.route('/')
def index():
    with session_scope() as session:
        suites = session.query(ArchiveSuite).all()

        return render_template('depcheck/index.html', suites=suites)


@depcheck.route('/<suite_name>/<ptype>/<arch_name>/<int:page>')
def issue_list(suite_name, ptype, arch_name, page):
    if ptype == 'binary':
        package_type = PackageType.BINARY
    else:
        package_type = PackageType.SOURCE

    with session_scope() as session:

        suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == suite_name) \
            .one_or_none()
        if not suite:
            abort(404)

        issues_per_page = 50
        issues_total = session.query(DebcheckIssue) \
            .filter(DebcheckIssue.package_type == package_type) \
            .filter(DebcheckIssue.suite_id == suite.id) \
            .filter(DebcheckIssue.architectures.any(arch_name)) \
            .count()
        page_count = math.ceil(issues_total / issues_per_page)

        issues = session.query(DebcheckIssue) \
            .filter(DebcheckIssue.package_type == package_type) \
            .filter(DebcheckIssue.suite_id == suite.id) \
            .filter(DebcheckIssue.architectures.any(arch_name)) \
            .order_by(DebcheckIssue.package_name) \
            .slice((page - 1) * issues_per_page, page * issues_per_page) \
            .all()

        return render_template('depcheck/issues_list.html',
                               ptype=ptype,
                               issues=issues,
                               suite=suite,
                               arch_name=arch_name,
                               issues_per_page=issues_per_page,
                               issues_total=issues_total,
                               current_page=page,
                               page_count=page_count)


@depcheck.route('/<suite_name>/issue/<uuid>')
def issue_details(suite_name, uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name == suite_name) \
            .one_or_none()
        if not suite:
            abort(404)

        issue = session.query(DebcheckIssue) \
            .filter(DebcheckIssue.suite_id == suite.id) \
            .filter(DebcheckIssue.uuid == uuid) \
            .one_or_none()
        if not issue:
            abort(404)

        # cache information (as it has to be decoded from json)
        missing = issue.missing
        conflicts = issue.conflicts
        ptype = 'source' if issue.package_type == PackageType.SOURCE else 'binary'

        return render_template('depcheck/issue.html',
                               PackageType=PackageType,
                               ptype=ptype,
                               issue=issue,
                               arch_name=', '.join(issue.architectures),
                               suite=suite,
                               missing=missing,
                               conflicts=conflicts)
