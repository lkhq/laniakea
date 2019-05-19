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
from laniakea.db import session_scope, SoftwareComponent
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
def details(cid):
    with session_scope() as session:
        # FIXME: Fetch all components with the ID and display them by version
        sw = session.query(SoftwareComponent) \
            .filter(SoftwareComponent.cid == cid) \
            .first()
        if not sw:
            abort(404)

        # parse AppStream metadata
        # FIXME: Inefficient!!!
        cpt = sw.load()

        screenshots = cpt.get_screenshots()

        return render_template('software/sw_details.html',
                               AppStream=AppStream,
                               screenshot_get_orig_image_url=screenshot_get_orig_image_url,
                               sw=sw,
                               cpt=cpt,
                               screenshots=screenshots)
