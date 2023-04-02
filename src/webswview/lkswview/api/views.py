# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, abort
from flask_restful import Api, Resource
from sqlalchemy.orm import undefer

from laniakea.db import ArchiveSuite, SourcePackage, session_scope
from laniakea.archive import repo_suite_settings_for

api = Blueprint('api', __name__, url_prefix='/api')
api_wrap = Api(api)


class TodoItem(Resource):
    def get(self, id):
        return {'task': 'Say "Hello, World!"'}


class SrcPackage(Resource):
    def get(self, repo_name, suite_name, name):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
            if not rss:
                abort(404)

            spkgs = (
                session.query(SourcePackage)
                .options(undefer(SourcePackage.version))
                .filter(SourcePackage.repo_id == rss.repo_id)
                .filter(SourcePackage.suites.any(ArchiveSuite.id == rss.suite_id))
                .filter(SourcePackage.name == name)
                .filter(SourcePackage.time_deleted.is_(None))
                .order_by(SourcePackage.version.desc())
                .all()
            )
            if not spkgs:
                abort(404)

            repo = rss.repo

            return {
                'pkgs': [
                    {
                        'uuid': spkg.uuid,
                        'source_uuid': spkg.source_uuid,
                        'name': spkg.name,
                        'version': spkg.version,
                        # skipping repo because presumably it's same as rss.repo
                        'suites': [suite.name for suite in spkg.suites],
                        'time_added': spkg.time_added,
                        'time_published': spkg.time_published,
                        'architectures': spkg.architectures,
                        'maintainer': spkg.maintainer,
                        'original_maintainer': spkg.original_maintainer,
                        'uploaders': spkg.uploaders,
                        'changes_urgency': spkg.changes_urgency,
                    }
                    for spkg in spkgs
                ],
                'pkg_repo': {
                    'name': repo.name,
                    'origin_name': repo.origin_name,
                },
            }


class Suite(Resource):
    def get(self, repo_name, suite_name):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
            if not rss:
                abort(404)

            suite = rss.suite

            return {
                'name': suite.name,
                'alias': suite.alias,
                'summary': suite.summary,
                'version': suite.version,
                'architectures': [{'name': arch.name} for arch in suite.architectures],
            }


api_wrap.add_resource(TodoItem, '/todos/<int:id>')
api_wrap.add_resource(SrcPackage, '/packages/src/<repo_name>/<suite_name>/<name>')
api_wrap.add_resource(Suite, '/suites/<repo_name>/<suite_name>')
