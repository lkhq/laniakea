# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

import gi
from flask import Blueprint, abort, flash, request, url_for, redirect, render_template
from sqlalchemy import String, cast, func
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects.postgresql import ARRAY

import laniakea.typing as T
from laniakea.db import (
    ArchiveSuite,
    ArchiveConfig,
    BinaryPackage,
    ArchiveSection,
    ArchiveRepository,
    SoftwareComponent,
    session_scope,
)

from ..extensions import cache

gi.require_version('AppStream', '1.0')
from gi.repository import AppStream

portal = Blueprint('portal', __name__)


@portal.route('/')
def index():
    return render_template('index.html')


@portal.route('/search_pkg', methods=['GET', 'POST'])
def search_pkg():
    term = request.args.get('term')
    if not term:
        flash('The search term was invalid.')
        return redirect(url_for('portal.index'))

    with session_scope() as session:
        q = (
            session.query(BinaryPackage)
            .filter(BinaryPackage.__ts_vector__.op('@@')(func.plainto_tsquery(term)))
            .distinct(BinaryPackage.name, BinaryPackage.version)
        )

        results_count = q.count()
        packages = q.all()

        results_per_page = results_count
        page_count = math.ceil(results_count / results_per_page) if results_per_page > 0 else 1

        return render_template(
            'pkg_search_results.html',
            term=term,
            results_count=results_count,
            results_per_page=results_per_page,
            page_count=page_count,
            packages=packages,
        )


@portal.route('/search_sw', methods=['GET', 'POST'])
def search_software():
    term = request.args.get('term')
    if not term:
        flash('The search term was invalid.')
        return redirect(url_for('portal.index'))

    with session_scope() as session:
        q = (
            session.query(SoftwareComponent)
            .join(SoftwareComponent.pkgs_binary)
            .filter(SoftwareComponent.__ts_vector__.op('@@')(func.plainto_tsquery(term)))
            .order_by(SoftwareComponent.cid, BinaryPackage.version.desc())
            .distinct(SoftwareComponent.cid)
        )

        results_count = q.count()
        software = q.all()

        results_per_page = results_count
        page_count = math.ceil(results_count / results_per_page) if results_per_page > 0 else 1

        return render_template(
            'software_search_results.html',
            term=term,
            results_count=results_count,
            results_per_page=results_per_page,
            page_count=page_count,
            software=software,
        )


@portal.route('/repos', defaults={'repo_name': None})
@portal.route('/repo/<repo_name>')
@cache.cached(timeout=8400)
def repo_index(repo_name: T.Optional[str] = None):
    with session_scope() as session:
        if not repo_name:
            selected_repo = session.query(ArchiveRepository).join(ArchiveConfig.primary_repo).one()
        else:
            selected_repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
        if not selected_repo:
            abort(404)
        repos = session.query(ArchiveRepository).order_by(ArchiveRepository.name).all()

        return render_template('repo_index.html', repos=repos, selected_repo=selected_repo)


@portal.route('/suite/<suite_name>/sections')
@cache.cached(timeout=8400)
def sections_index(suite_name):
    with session_scope() as session:
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one_or_none()
        if not suite:
            abort(404)

        sections = session.query(ArchiveSection).order_by(ArchiveSection.name).all()
        return render_template('sections_index.html', suite=suite, sections=sections)


@portal.route('/suite/<suite_name>/<section_name>/<int:page>')
@cache.cached(timeout=3600)
def section_view(suite_name, section_name, page):
    with session_scope() as session:
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one_or_none()
        if not suite:
            abort(404)

        pkgs_per_page = 50
        pkg_query = (
            session.query(BinaryPackage)
            .filter(BinaryPackage.suites.any(ArchiveSuite.id == suite.id))
            .filter(BinaryPackage.section == section_name)
            .distinct(BinaryPackage.name, BinaryPackage.version)
            .order_by(BinaryPackage.name)
        )
        pkgs_total = pkg_query.count()
        page_count = math.ceil(pkgs_total / pkgs_per_page)

        packages = (
            pkg_query.options(joinedload(BinaryPackage.component))
            .slice((page - 1) * pkgs_per_page, page * pkgs_per_page)
            .all()
        )

        return render_template(
            'section_view.html',
            section_name=section_name,
            suite=suite,
            packages=packages,
            pkgs_per_page=pkgs_per_page,
            pkgs_total=pkgs_total,
            current_page=page,
            page_count=page_count,
        )


# cached app category dictionary
_app_categories = None


def get_app_categories():
    '''
    Retrieve a cached dict of software categories.
    '''
    global _app_categories
    if _app_categories:
        return _app_categories

    cats = {}
    ascats = AppStream.get_default_categories(False)
    for c in ascats:
        cats[c.get_id()] = c
    _app_categories = cats
    return cats


@portal.route('/categories')
@cache.cached(timeout=8400)
def categories_index():
    categories = get_app_categories()
    return render_template('categories_index.html', categories=categories.values())


@portal.route('/category/<cat_id>/<subcat_id>/<int:page>')
@portal.route('/category/<cat_id>/<int:page>', defaults={'subcat_id': None})
@cache.cached(timeout=8400)
def category_view(cat_id, subcat_id, page):
    categories = get_app_categories()
    category = categories.get(cat_id)
    if not category:
        abort(404)

    parent_category = category
    if subcat_id:
        category = None
        for c in parent_category.get_children():
            if c.get_id() == subcat_id:
                category = c
                break
        if not category:
            abort(404)

    sw_per_page = 25

    with session_scope() as session:
        # TODO: Do this inefficient filtering in advance
        dcats = []
        for c in category.get_desktop_groups():
            parts = c.split('::')
            if len(parts) <= 1:
                dcats.append(c)
            else:
                dcats.append(parts[-1])

        sw_query = (
            session.query(SoftwareComponent)
            .join(SoftwareComponent.pkgs_binary)
            .filter(SoftwareComponent.categories.overlap(cast(dcats, ARRAY(String()))))
            .order_by(SoftwareComponent.cid, BinaryPackage.version.desc())
            .distinct(SoftwareComponent.cid)
        )
        software = sw_query.slice((page - 1) * sw_per_page, page * sw_per_page).all()

        sw_total = sw_query.count()
        page_count = math.ceil(sw_total / sw_per_page)

        return render_template(
            'category_view.html',
            parent_category=parent_category,
            category=category,
            subcat_id=subcat_id,
            software=software,
            sw_per_page=sw_per_page,
            sw_total=sw_total,
            current_page=page,
            page_count=page_count,
        )
