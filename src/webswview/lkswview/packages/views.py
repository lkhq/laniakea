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

from flask import Blueprint, render_template, abort
from laniakea.db import session_scope, BinaryPackage

packages = Blueprint('packages',
                     __name__,
                     url_prefix='/package')


@packages.route('/bin/<name>/<version>')
def bin_package_details(name, version):
    with session_scope() as session:
        bpkgs = session.query(BinaryPackage) \
            .filter(BinaryPackage.name == name) \
            .filter(BinaryPackage.version == version) \
            .all()
        if not bpkgs:
            abort(404)

        suites = set()
        architectures = set()
        for bpkg in bpkgs:
            suites.update(bpkg.suites)
            architectures.add(bpkg.architecture)

        return render_template('packages/bin_details.html',
                               pkg=bpkgs[0],
                               suites=suites,
                               architectures=architectures)
