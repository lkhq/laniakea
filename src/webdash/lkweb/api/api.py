# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask_rebar import Rebar, SwaggerV3Generator, errors
from marshmallow import Schema, fields
from sqlalchemy.orm import undefer, joinedload

from laniakea.db import (
    ArchiveSuite,
    SourcePackage,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import repo_suite_settings_for

rebar = Rebar()

# All handler URL rules will be prefixed by '/v1'
registry = rebar.create_handler_registry(
    prefix='/api/v1',
    spec_path='/docs',
    swagger_ui_path='/docs/ui',
    swagger_generator=SwaggerV3Generator(title='Laniakea API'),
)


class RepositorySchema(Schema):
    id = fields.Integer()

    name = fields.String()
    origin_name = fields.String()
    is_debug = fields.Boolean()
    upload_suite_map = fields.Dict(keys=fields.String(), values=fields.String())


class ArchitectureSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    summary = fields.String()


class RepoComponentSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    summary = fields.String()

    parent_component = fields.Nested(lambda: RepoComponentSchema(exclude=('parent_component',)))


class SuiteSchema(Schema):
    id = fields.Integer()

    name = fields.String()
    alias = fields.String()
    summary = fields.String()
    version = fields.String()
    dbgsym_policy = fields.String()

    architectures = fields.Nested(ArchitectureSchema(only=('id', 'name'), many=True))
    components = fields.Nested(RepoComponentSchema(only=('id', 'name'), many=True))

    debug_suite_for = fields.Nested(lambda: SuiteSchema(only=('id', 'name')))
    parents = fields.Nested(lambda: SuiteSchema(only=('id', 'name'), many=True))


class RepoSuiteSettingsSchema(Schema):
    id = fields.Integer()
    repo = fields.Nested(RepositorySchema(only=('id', 'name')))
    suite = fields.Nested(SuiteSchema(only=('id', 'name')))

    suite_summary = fields.String()
    accept_uploads = fields.Boolean()
    new_policy = fields.String()
    devel_target = fields.Boolean()
    frozen = fields.Boolean()
    auto_overrides = fields.Boolean()
    manual_accept = fields.Boolean()
    not_automatic = fields.Boolean()
    but_automatic_upgrades = fields.Boolean()
    valid_time = fields.Integer()
    phased_update_delay = fields.Integer()
    signingkeys = fields.List(fields.String())
    announce_emails = fields.List(fields.String())
    changes_pending = fields.Boolean()
    time_published = fields.String()


class SourcePackageSchema(Schema):
    uuid = fields.String()
    source_uuid = fields.String()

    name = fields.String()
    version = fields.String()

    repo_id = fields.Integer()

    suites = fields.Nested(SuiteSchema(only=('id', 'name'), many=True))
    component = fields.Nested(RepoComponentSchema(only=('id', 'name')))

    time_added = fields.String()  # DateTime
    time_published = fields.String()  # DateTime
    time_deleted = fields.String()  # DateTime

    section_id = fields.Integer()
    architectures = fields.List(fields.String())

    standards_version = fields.String()
    format_version = fields.String()

    maintainer = fields.String()
    original_maintainer = fields.String()
    uploaders = fields.List(fields.String())

    homepage = fields.String()
    vcs_browser = fields.String()
    vcs_git = fields.String()

    summary = fields.String()
    description = fields.String()

    testsuite = fields.List(fields.String())
    testsuite_triggers = fields.List(fields.String())

    changes_urgency = fields.String()

    build_depends = fields.List(fields.String())
    build_depends_indep = fields.List(fields.String())
    build_depends_arch = fields.List(fields.String())

    build_conflicts = fields.List(fields.String())
    build_conflicts_indep = fields.List(fields.String())
    build_conflicts_arch = fields.List(fields.String())

    directory = fields.String()


@registry.handles(rule='/repos', method='GET', response_body_schema=RepositorySchema(many=True))
def get_repo_infos():
    """
    Retrieve information about all repositories.
    """

    with session_scope() as session:
        repos = session.query(ArchiveRepository).all()
        if not repos:
            raise errors.NotFound()

        schema = RepositorySchema(many=True)
        return schema.dump(repos)


@registry.handles(rule='/suites', method='GET', response_body_schema=SuiteSchema(many=True))
def get_suite_infos():
    """
    Retrieve information about all suites.
    """

    with session_scope() as session:
        suites = (
            session.query(ArchiveSuite)
            .options(
                joinedload(ArchiveSuite.architectures),
                joinedload(ArchiveSuite.components),
                joinedload(ArchiveSuite.debug_suite_for),
            )
            .all()
        )
        if not suites:
            raise errors.NotFound()

        schema = SuiteSchema(many=True)
        return schema.dump(suites)


@registry.handles(rule='/repo_suites', method='GET', response_body_schema=RepoSuiteSettingsSchema(many=True))
def get_repo_suite_infos():
    """
    Retrieve details about suites present in individual repositories, as well as their configuration.
    """

    with session_scope() as session:
        rss_seq = (
            session.query(ArchiveRepoSuiteSettings)
            .options(joinedload(ArchiveRepoSuiteSettings.repo), joinedload(ArchiveRepoSuiteSettings.suite))
            .all()
        )
        if not rss_seq:
            raise errors.NotFound()

        schema = RepoSuiteSettingsSchema(many=True)
        return schema.dump(rss_seq)


@registry.handles(
    rule='/pkg/src/by-name/<repo_name>/<suite_name>/<name>',
    method='GET',
    response_body_schema=SourcePackageSchema(many=True),
)
def get_package_source(repo_name: str, suite_name: str, name: str):
    """
    Retrieve details about a particular source package.

    :param repo_name: Name of the repository.
    """

    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
        if not rss:
            raise errors.NotFound()

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
            raise errors.NotFound()

        schema = SourcePackageSchema(many=True)
        return schema.dump(spkgs)
