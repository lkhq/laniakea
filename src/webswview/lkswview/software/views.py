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

from flask import current_app, Blueprint, render_template, abort
from laniakea.db import session_scope, BinaryPackage, SoftwareComponent
from sqlalchemy.orm import joinedload
from ..extensions import cache
import gi
gi.require_version('AppStream', '1.0')
from gi.repository import AppStream

software = Blueprint('software',
                     __name__,
                     url_prefix='/sw')


def screenshot_get_orig_image_url(scr):
    for img in scr.get_images():
        if img.get_kind() == AppStream.ImageKind.SOURCE:
            return current_app.config['APPSTREAM_MEDIA_URL'] + '/' + img.get_url()
    return '#'


@software.route('/<cid>')
@cache.cached(timeout=240)
def details(cid):
    with session_scope() as session:
        # NOTE: We display the newest component here. Maybe we want to actually
        # display the different component data by-version?
        sws = session.query(SoftwareComponent) \
            .options(joinedload(SoftwareComponent.bin_packages)
                     .joinedload(BinaryPackage.suites)) \
            .join(SoftwareComponent.bin_packages) \
            .filter(SoftwareComponent.cid == cid) \
            .order_by(BinaryPackage.version.desc()) \
            .all()
        if not sws:
            abort(404)

        # FIXME: This loop is probably inefficient...
        packages_map = dict()
        for sw in sws:
            for bpkg in sw.bin_packages:
                for suite in bpkg.suites:
                    if suite.name not in packages_map:
                        packages_map[suite.name] = list()
                    packages_map[suite.name].append(bpkg)

        # grab the most recent component
        sw = sws[0]

        # parse AppStream metadata
        # FIXME: Parsing XML is expensive, we can cache this aggressively
        cpt = sw.load()

        screenshots = cpt.get_screenshots()

        return render_template('software/sw_details.html',
                               AppStream=AppStream,
                               screenshot_get_orig_image_url=screenshot_get_orig_image_url,
                               sw=sw,
                               cpt=cpt,
                               component_id=cid,
                               packages_map=packages_map,
                               screenshots=screenshots)
