# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math
import humanize
from flask import current_app, Blueprint, render_template, abort, url_for
from laniakea.db import session_scope, BinaryPackage, SourcePackage, ArchiveSuite, \
    Job, JobStatus, JobResult, SparkWorker, ArchiveArchitecture, DebcheckIssue, \
    PackageType, SpearsExcuse
from sqlalchemy.orm import undefer, joinedload
from sqlalchemy import or_
from laniakea.utils import get_dir_shorthand_for_uuid
from ..extensions import cache
from ..utils import humanized_timediff, is_uuid

packages = Blueprint('packages',
                     __name__,
                     url_prefix='/package')


@cache.memoize(1800)
def make_linked_dependency(suite_name, depstr):
    if not depstr:
        return depstr
    deps = [d.strip() for d in depstr.split('|')]

    dep_urls = []
    for dep in deps:
        parts = dep.split(' ', 1)
        pkgname = parts[0]
        versioning = parts[1].strip() if len(parts) > 1 else ''

        url = '<a href="{url}">{pkgname}</a> {versioning}'.format(url=url_for('packages.bin_package_details', suite_name=suite_name, name=pkgname),
                                                                  pkgname=pkgname,
                                                                  versioning=versioning)
        dep_urls.append(url)

    return ' | '.join(dep_urls)


@cache.memoize(3600)
def all_architectures():
    with session_scope() as session:
        arches = session.query(ArchiveArchitecture) \
                        .options(undefer(ArchiveArchitecture.id)) \
                        .options(undefer(ArchiveArchitecture.name)) \
                        .all()
        for a in arches:
            session.expunge(a)
        return arches


@cache.memoize(1800)
def link_for_bin_package_id(suite_name, pkgstr):
    if not pkgstr:
        return pkgstr
    parts = pkgstr.split(':', 1)
    pkgname = parts[0]
    extra = parts[1].strip() if len(parts) > 1 else ''

    url = '<a href="{url}">{pkgname}</a> {extra}'.format(url=url_for('packages.bin_package_details', suite_name=suite_name, name=pkgname),
                                                         pkgname=pkgname,
                                                         extra=extra)
    return url


@cache.memoize(600)
def architectures_with_issues_for_spkg(suite, spkg):
    with session_scope() as session:
        results = session.query(DebcheckIssue.architectures.distinct()) \
                         .filter(DebcheckIssue.package_type == PackageType.SOURCE) \
                         .filter(DebcheckIssue.suite_id == suite.id) \
                         .filter(DebcheckIssue.package_name == spkg.name) \
                         .filter(DebcheckIssue.package_version == spkg.version) \
                         .all()
        arches = set()
        for r in results:
            arches.update(r[0])
        return arches


@cache.memoize(600)
def migration_excuse_info(spkg, suite_name):
    with session_scope() as session:
        qres = session.query(SpearsExcuse.uuid,
                             SpearsExcuse.version_new,
                             SpearsExcuse.suite_source,
                             SpearsExcuse.suite_target,
                             SpearsExcuse.age_current,
                             SpearsExcuse.age_required) \
                      .filter(or_(SpearsExcuse.suite_source == suite_name,
                                  SpearsExcuse.suite_target == suite_name,)) \
                      .filter(SpearsExcuse.source_package == spkg.name) \
                      .all()
        if not qres:
            return []
        infos = []
        for e in qres:
            if e[4] is None:
                continue
            stuck = e[4] >= e[5]
            infos.append({'uuid': e[0],
                          'version_new': e[1],
                          'source': e[2],
                          'target': e[3],
                          'stuck': stuck})
        return infos


@packages.route('/bin/<suite_name>/<name>')
@cache.cached(timeout=120)
def bin_package_details(suite_name, name):
    with session_scope() as session:
        suite = session.query(ArchiveSuite) \
                       .filter(ArchiveSuite.name == suite_name) \
                       .one_or_none()
        if not suite:
            abort(404)

        bpkgs = session.query(BinaryPackage) \
                       .options(joinedload(BinaryPackage.architecture)) \
                       .options(joinedload(BinaryPackage.bin_file)) \
                       .options(undefer(BinaryPackage.version)) \
                       .filter(BinaryPackage.name == name) \
                       .filter(BinaryPackage.suites.any(ArchiveSuite.id == suite.id)) \
                       .order_by(BinaryPackage.version.desc()).all()
        if not bpkgs:
            abort(404)

        suites = [s[0] for s in session.query(ArchiveSuite.name.distinct())
                                       .filter(ArchiveSuite.bin_packages.any(BinaryPackage.name == name))
                                       .all()]

        architectures = set()
        bpkg_rep = bpkgs[0]  # the first package is always the most recent one
        for bpkg in bpkgs:
            architectures.add(bpkg.architecture)
        if not bpkg_rep:
            abort(404)

        dep_issues = session.query(DebcheckIssue) \
                            .filter(DebcheckIssue.package_type == PackageType.BINARY) \
                            .filter(DebcheckIssue.suite_id == suite.id) \
                            .filter(DebcheckIssue.package_name == bpkg_rep.name) \
                            .filter(DebcheckIssue.package_version == bpkg_rep.version) \
                            .all()

        return render_template('packages/bin_details.html',
                               pkg=bpkg_rep,
                               pkgs_all=bpkgs,
                               pkg_suite_name=suite_name,
                               suites=suites,
                               architectures=architectures,
                               dep_issues=dep_issues,
                               naturalsize=humanize.naturalsize,
                               make_linked_dependency=make_linked_dependency,
                               link_for_bin_package_id=link_for_bin_package_id)


@packages.route('/src/<suite_name>/<name>')
@cache.cached(timeout=120)
def src_package_details(suite_name, name):
    with session_scope() as session:
        suite = session.query(ArchiveSuite) \
                       .filter(ArchiveSuite.name == suite_name) \
                       .one_or_none()
        if not suite:
            abort(404)

        spkgs = session.query(SourcePackage) \
                       .options(undefer(SourcePackage.version)) \
                       .filter(SourcePackage.suites.any(ArchiveSuite.id == suite.id)) \
                       .filter(SourcePackage.name == name) \
                       .order_by(SourcePackage.version.desc()) \
                       .all()
        if not spkgs:
            abort(404)

        suites = [s[0] for s in session.query(ArchiveSuite.name.distinct())
                                       .filter(ArchiveSuite.src_packages.any(SourcePackage.name == name))
                                       .all()]
        spkg_rep = spkgs[0]  # the first package is always the most recent one

        broken_archs = architectures_with_issues_for_spkg(suite, spkg_rep)
        migration_infos = migration_excuse_info(spkg_rep, suite_name)

        return render_template('packages/src_details.html',
                               pkg=spkg_rep,
                               pkgs_all=spkgs,
                               pkg_suite_name=suite_name,
                               suites=suites,
                               broken_archs=broken_archs,
                               migration_infos=migration_infos,
                               make_linked_dependency=make_linked_dependency)


@packages.route('/builds/<name>/<int:page>')
@cache.cached(timeout=50)
def builds_list(name, page):
    with session_scope() as session:
        spkg = session.query(SourcePackage) \
            .filter(SourcePackage.name == name) \
            .order_by(SourcePackage.version.desc()) \
            .first()
        if not spkg:
            abort(404)

        jobs_per_page = 20
        jobs_query = session.query(Job) \
                            .filter(Job.trigger == spkg.source_uuid) \
                            .order_by(Job.time_created.desc())
        jobs_total = jobs_query.count()
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs_list = jobs_query.slice((page - 1) * jobs_per_page, page * jobs_per_page) \
                              .all()

        # create by-architecture view on jobs
        jobs_arch = {}
        for arch in all_architectures():
            jobs_arch[arch.name] = []
        for j in jobs_list:
            if j.architecture not in jobs_arch:
                jobs_arch[j.architecture] = []
            jobs_arch[j.architecture].append(j)

        return render_template('packages/builds_list.html',
                               JobStatus=JobStatus,
                               JobResult=JobResult,
                               humanized_timediff=humanized_timediff,
                               pkg=spkg,
                               jobs_arch=jobs_arch,
                               jobs_per_page=jobs_per_page,
                               jobs_total=jobs_total,
                               current_page=page,
                               page_count=page_count)


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
            log_url = current_app.config['LOG_STORAGE_URL'] + '/' + get_dir_shorthand_for_uuid(job.uuid) + '/' + str(job.uuid) + '.log'

        spkg = session.query(SourcePackage) \
            .filter(SourcePackage.source_uuid == job.trigger) \
            .filter(SourcePackage.version == job.version) \
            .one_or_none()
        if not spkg:
            abort(404)

        suite_name = 'unknown'
        if job.data:
            suite = session.query(ArchiveSuite) \
                           .filter(ArchiveSuite.name == job.data.get('suite')) \
                           .one_or_none()
            suite_name = suite.name

        dep_issues = session.query(DebcheckIssue) \
                            .filter(DebcheckIssue.package_type == PackageType.SOURCE) \
                            .filter(DebcheckIssue.suite_id == suite.id) \
                            .filter(DebcheckIssue.package_name == spkg.name) \
                            .filter(DebcheckIssue.package_version == spkg.version) \
                            .filter(DebcheckIssue.architectures.overlap([job.architecture, 'any'])) \
                            .all()

        return render_template('packages/build_details.html',
                               humanized_timediff=humanized_timediff,
                               JobStatus=JobStatus,
                               JobResult=JobResult,
                               job=job,
                               worker=worker,
                               spkg=spkg,
                               dep_issues=dep_issues,
                               suite_name=suite_name,
                               log_url=log_url,
                               link_for_bin_package_id=link_for_bin_package_id)


@packages.route('/excuses/<uuid>')
def view_excuse(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        excuse = session.query(SpearsExcuse).filter(SpearsExcuse.uuid == uuid).one_or_none()
        if not excuse:
            abort(404)

        return render_template('packages/excuse_details.html',
                               excuse=excuse,
                               link_for_bin_package_id=link_for_bin_package_id)
