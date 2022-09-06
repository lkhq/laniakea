# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

import humanize
from flask import Blueprint, abort, url_for, current_app, render_template
from sqlalchemy.orm import undefer, joinedload

from laniakea.db import (
    Job,
    JobResult,
    JobStatus,
    PackageType,
    SparkWorker,
    ArchiveSuite,
    SpearsExcuse,
    BinaryPackage,
    DebcheckIssue,
    SourcePackage,
    PackagePriority,
    ArchiveRepository,
    ArchiveArchitecture,
    SpearsMigrationTask,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.utils import get_dir_shorthand_for_uuid
from laniakea.archive import repo_suite_settings_for

from ..utils import is_uuid, humanized_timediff
from ..extensions import cache

packages = Blueprint('packages', __name__, url_prefix='/package')


@cache.memoize(1800)
def make_linked_dependency(repo: ArchiveRepository, suite: ArchiveSuite, depstr: str):
    if not depstr:
        return depstr
    deps = [d.strip() for d in depstr.split('|')]

    dep_urls = []
    with session_scope() as session:
        for dep in deps:
            parts = dep.split(' ', 1)
            pkgname = parts[0]
            versioning = parts[1].strip() if len(parts) > 1 else ''

            exq = (
                session.query(BinaryPackage)
                .filter(BinaryPackage.repo.has(id=repo.id))
                .filter(BinaryPackage.name == pkgname)
                .exists()
            )
            if session.query(exq).scalar():
                url = '<a href="{url}">{pkgname}</a> {versioning}'.format(
                    url=url_for(
                        'packages.bin_package_details', repo_name=repo.name, suite_name=suite.name, name=pkgname
                    ),
                    pkgname=pkgname,
                    versioning=versioning,
                )
            else:
                url = '{pkgname} {versioning}'.format(
                    pkgname=pkgname,
                    versioning=versioning,
                )
            dep_urls.append(url)

    return ' | '.join(dep_urls)


@cache.memoize(3600)
def all_architectures():
    with session_scope() as session:
        arches = (
            session.query(ArchiveArchitecture)
            .options(undefer(ArchiveArchitecture.id))
            .options(undefer(ArchiveArchitecture.name))
            .all()
        )
        for a in arches:
            session.expunge(a)
        return arches


@cache.memoize(1800)
def link_for_bin_package_id(repo_name: str, suite_name: str, pkgstr: str):
    if not pkgstr:
        return pkgstr
    parts = pkgstr.split(':', 1)
    pkgname = parts[0]
    extra = parts[1].strip() if len(parts) > 1 else ''

    url = '<a href="{url}">{pkgname}</a> {extra}'.format(
        url=url_for('packages.bin_package_details', repo_name=repo_name, suite_name=suite_name, name=pkgname),
        pkgname=pkgname,
        extra=extra,
    )
    return url


@cache.memoize(600)
def architectures_with_issues_for_spkg(rss: ArchiveRepoSuiteSettings, spkg: SourcePackage):
    with session_scope() as session:
        results = (
            session.query(DebcheckIssue.architectures.distinct())
            .filter(DebcheckIssue.package_type == PackageType.SOURCE)
            .filter(DebcheckIssue.repo_id == rss.repo_id)
            .filter(DebcheckIssue.suite_id == rss.suite_id)
            .filter(DebcheckIssue.package_name == spkg.name)
            .filter(DebcheckIssue.package_version == spkg.version)
            .all()
        )
        arches = set()
        for r in results:
            arches.update(r[0])
        return arches


@cache.memoize(600)
def migration_excuse_info(rss: ArchiveRepoSuiteSettings, spkg: SourcePackage):
    with session_scope() as session:
        smtask = (
            session.query(SpearsMigrationTask)
            .filter(SpearsMigrationTask.source_suites.any(ArchiveSuite.id == rss.suite_id))
            .filter(SpearsMigrationTask.target_suite.has(id=rss.suite_id))
            .first()
        )
        if not smtask:
            return []
        qres = (
            session.query(
                SpearsExcuse.uuid,
                SpearsExcuse.version_new,
                SpearsExcuse.age_current,
                SpearsExcuse.age_required,
            )
            .filter(SpearsExcuse.source_package_id == spkg.uuid)
            .filter(SpearsExcuse.migration_id == smtask.id)
            .all()
        )
        if not qres:
            return []
        infos = []
        for e in qres:
            if e[2] is None:
                continue
            stuck = e[2] >= e[3]
            infos.append(
                {
                    'uuid': e[0],
                    'version_new': e[1],
                    'source': '×'.join([s.name for s in smtask.source_suites]),
                    'target': smtask.target_suite.name,
                    'stuck': stuck,
                }
            )
        return infos


@packages.route('/bin/<repo_name>/<suite_name>/<name>')
@cache.cached(timeout=120)
def bin_package_details(repo_name, suite_name, name):
    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
        if not rss:
            abort(404)

        bpkgs = (
            session.query(BinaryPackage)
            .options(joinedload(BinaryPackage.architecture))
            .options(joinedload(BinaryPackage.bin_file))
            .options(undefer(BinaryPackage.version))
            .filter(BinaryPackage.name == name)
            .filter(BinaryPackage.repo_id == rss.repo_id)
            .filter(BinaryPackage.suites.any(ArchiveSuite.id == rss.suite_id))
            .order_by(BinaryPackage.version.desc())
            .all()
        )
        if not bpkgs:
            abort(404)

        suites = [
            s[0]
            for s in session.query(ArchiveSuite.name.distinct())
            .filter(ArchiveSuite.pkgs_binary.any(BinaryPackage.name == name))
            .filter(ArchiveSuite.pkgs_binary.any(BinaryPackage.repo_id == rss.repo_id))
            .all()
        ]

        architectures = set()
        bpkg_rep = bpkgs[0]  # the first package is always the most recent one
        for bpkg in bpkgs:
            architectures.add(bpkg.architecture)
        if not bpkg_rep:
            abort(404)

        dep_issues = (
            session.query(DebcheckIssue)
            .filter(DebcheckIssue.package_type == PackageType.BINARY)
            .filter(DebcheckIssue.repo_id == rss.repo_id)
            .filter(DebcheckIssue.suite_id == rss.suite_id)
            .filter(DebcheckIssue.package_name == bpkg_rep.name)
            .filter(DebcheckIssue.package_version == bpkg_rep.version)
            .all()
        )

        return render_template(
            'packages/bin_details.html',
            pkg=bpkg_rep,
            pkg_description=bpkg_rep.description.split('\n', 1)[1].replace('\n', '<br/>'),
            pkgs_all=bpkgs,
            pkg_repo=rss.repo,
            pkg_suite=rss.suite,
            suites=suites,
            architectures=architectures,
            dep_issues=dep_issues,
            naturalsize=humanize.naturalsize,
            make_linked_dependency=make_linked_dependency,
            link_for_bin_package_id=link_for_bin_package_id,
            PackagePriority=PackagePriority,
        )


@packages.route('/src/<repo_name>/<suite_name>/<name>')
@cache.cached(timeout=120)
def src_package_details(repo_name, suite_name, name):
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
            .order_by(SourcePackage.version.desc())
            .all()
        )
        if not spkgs:
            abort(404)

        suites = [
            s[0]
            for s in session.query(ArchiveSuite.name.distinct())
            .filter(ArchiveSuite.pkgs_source.any(SourcePackage.name == name))
            .all()
        ]
        spkg_rep = spkgs[0]  # the first package is always the most recent one

        broken_archs = architectures_with_issues_for_spkg(rss, spkg_rep)
        migration_infos = migration_excuse_info(rss, spkg_rep)

        return render_template(
            'packages/src_details.html',
            pkg=spkg_rep,
            pkgs_all=spkgs,
            pkg_repo=rss.repo,
            pkg_suite=rss.suite,
            suites=suites,
            broken_archs=broken_archs,
            migration_infos=migration_infos,
            make_linked_dependency=make_linked_dependency,
        )


@packages.route('/builds/<name>/<int:page>')
@cache.cached(timeout=50)
def builds_list(name, page):
    with session_scope() as session:
        spkg = (
            session.query(SourcePackage)
            .filter(SourcePackage.name == name)
            .order_by(SourcePackage.version.desc())
            .first()
        )
        if not spkg:
            abort(404)

        jobs_per_page = 20
        jobs_query = session.query(Job).filter(Job.trigger == spkg.source_uuid).order_by(Job.time_created.desc())
        jobs_total = jobs_query.count()
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs_list = jobs_query.slice((page - 1) * jobs_per_page, page * jobs_per_page).all()

        # create by-architecture view on jobs
        jobs_arch = {}
        for arch in all_architectures():
            jobs_arch[arch.name] = []
        for j in jobs_list:
            if j.architecture not in jobs_arch:
                jobs_arch[j.architecture] = []
            jobs_arch[j.architecture].append(j)

        return render_template(
            'packages/builds_list.html',
            JobStatus=JobStatus,
            JobResult=JobResult,
            humanized_timediff=humanized_timediff,
            pkg=spkg,
            jobs_arch=jobs_arch,
            jobs_per_page=jobs_per_page,
            jobs_total=jobs_total,
            current_page=page,
            page_count=page_count,
        )


@packages.route('/builds/job/<uuid>')
@cache.cached(timeout=10)
def build_details(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid == uuid).one_or_none()
        if not job:
            abort(404)

        worker = session.query(SparkWorker).filter(SparkWorker.uuid == job.worker).one_or_none()

        log_url = None
        if job.result == JobResult.SUCCESS or job.result == JobResult.FAILURE:
            log_url = (
                current_app.config['LOG_STORAGE_URL']
                + '/'
                + get_dir_shorthand_for_uuid(job.uuid)
                + '/'
                + str(job.uuid)
                + '.log'
            )

        spkg = (
            session.query(SourcePackage)
            .filter(SourcePackage.source_uuid == job.trigger)
            .filter(SourcePackage.version == job.version)
            .one_or_none()
        )
        if not spkg:
            abort(404)

        suite_name = 'unknown'
        if job.data:
            suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == job.data.get('suite')).one_or_none()
            suite_name = suite.name

        dep_issues = (
            session.query(DebcheckIssue)
            .filter(DebcheckIssue.package_type == PackageType.SOURCE)
            .filter(DebcheckIssue.suite_id == suite.id)
            .filter(DebcheckIssue.package_name == spkg.name)
            .filter(DebcheckIssue.package_version == spkg.version)
            .filter(DebcheckIssue.architectures.overlap([job.architecture, 'any']))
            .all()
        )

        return render_template(
            'packages/build_details.html',
            humanized_timediff=humanized_timediff,
            JobStatus=JobStatus,
            JobResult=JobResult,
            job=job,
            worker=worker,
            spkg=spkg,
            dep_issues=dep_issues,
            suite_name=suite_name,
            log_url=log_url,
            link_for_bin_package_id=link_for_bin_package_id,
        )


@packages.route('/excuses/<uuid>')
def view_excuse(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        excuse = session.query(SpearsExcuse).filter(SpearsExcuse.uuid == uuid).one_or_none()
        if not excuse:
            abort(404)

        return render_template(
            'packages/excuse_details.html', excuse=excuse, link_for_bin_package_id=link_for_bin_package_id
        )
