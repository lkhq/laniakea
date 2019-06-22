# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import math
from flask import Blueprint, render_template, request, flash, redirect, url_for
from laniakea.db import session_scope, BinaryPackage, SoftwareComponent
from sqlalchemy.sql import func
from ..extensions import cache

portal = Blueprint('portal', __name__)


@portal.route('/')
def index():
    return render_template('index.html')


@portal.route('/search_pkg', methods=['GET', 'POST'])
@cache.cached(timeout=40)
def search_pkg():
    term = request.args.get('term')
    if not term:
        flash('The search term was invalid.')
        return redirect(url_for('portal.index'))

    with session_scope() as session:
        q = session.query(BinaryPackage) \
            .filter(BinaryPackage.__ts_vector__.op('@@')(func.plainto_tsquery(term))) \
            .distinct(BinaryPackage.name, BinaryPackage.version)

        results_count = q.count()
        packages = q.all()

        results_per_page = results_count
        page_count = math.ceil(results_count / results_per_page) if results_per_page > 0 else 1

        return render_template('pkg_search_results.html',
                               term=term,
                               results_count=results_count,
                               results_per_page=results_per_page,
                               page_count=page_count,
                               packages=packages)


@portal.route('/search_sw', methods=['GET', 'POST'])
@cache.cached(timeout=40)
def search_software():
    term = request.args.get('term')
    if not term:
        flash('The search term was invalid.')
        return redirect(url_for('portal.index'))

    with session_scope() as session:
        q = session.query(SoftwareComponent) \
            .filter(SoftwareComponent.__ts_vector__.op('@@')(func.plainto_tsquery(term))) \
            .distinct(SoftwareComponent.cid)

        results_count = q.count()
        software = q.all()

        results_per_page = results_count
        page_count = math.ceil(results_count / results_per_page) if results_per_page > 0 else 1

        return render_template('software_search_results.html',
                               term=term,
                               results_count=results_count,
                               results_per_page=results_per_page,
                               page_count=page_count,
                               software=software)
