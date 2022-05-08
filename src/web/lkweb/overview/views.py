# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, render_template

from laniakea import LocalConfig
from laniakea.db import (
    BinaryPackage,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)

overview = Blueprint('overview', __name__)


@overview.route('/')
def index():
    lconf = LocalConfig()
    with session_scope() as session:
        master_repo_id = (
            session.query(ArchiveRepository.id).filter(ArchiveRepository.name == lconf.master_repo_name).one()[0]
        )
        repo_count = session.query(ArchiveRepository.id).count()
        dev_target_rss = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(
                ArchiveRepoSuiteSettings.repo.has(id=master_repo_id),
                ArchiveRepoSuiteSettings.repo.has(is_debug=False),
                ArchiveRepoSuiteSettings.devel_target == True,
            )
            .first()
        )
        dev_target = None
        if dev_target_rss:
            dev_target = dev_target_rss.suite

        package_count = session.query(BinaryPackage.uuid).distinct(BinaryPackage.name).count()

        return render_template('index.html', repo_count=repo_count, dev_target=dev_target, package_count=package_count)
