# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import gi
from flask import Blueprint, abort, current_app, render_template
from sqlalchemy.orm import joinedload

from laniakea.db import BinaryPackage, SoftwareComponent, session_scope

from ..extensions import cache

gi.require_version('AppStream', '1.0')
from gi.repository import AppStream

software = Blueprint('software', __name__, url_prefix='/sw')


class ASComponent:
    """Helper class to work with raw AppStream data as JSON"""

    def __init__(self, data):
        self._d = data

    def url_for(self, kind: AppStream.UrlKind):
        return self._d.get('Url', {}).get(AppStream.url_kind_to_string(kind))

    @property
    def screenshots(self):
        return self._d.get('Screenshots', [])


def screenshot_get_orig_image_url(scr_data):
    img = scr_data.get('source-image')
    if img:
        return current_app.config['APPSTREAM_MEDIA_URL'] + '/' + img['url']
    return '#'


@software.route('/<cid>')
@cache.cached(timeout=240)
def details(cid):
    with session_scope() as session:
        # NOTE: We display the newest component here. Maybe we want to actually
        # display the different component data by-version?
        sws = (
            session.query(SoftwareComponent)
            .options(joinedload(SoftwareComponent.pkgs_binary).joinedload(BinaryPackage.suites))
            .join(SoftwareComponent.pkgs_binary)
            .filter(SoftwareComponent.cid == cid)
            .order_by(BinaryPackage.version.desc())
            .all()
        )
        if not sws:
            abort(404)

        # FIXME: This loop is probably inefficient...
        packages_map = dict()
        for sw in sws:
            for bpkg in sw.pkgs_binary:
                for suite in bpkg.suites:
                    if suite.name not in packages_map:
                        packages_map[suite.name] = list()
                    packages_map[suite.name].append(bpkg)

        # grab the most recent component
        sw = sws[0]

        # FIXME: We parse the whole component as JSON here - if this becomes a performance issue,
        # we could parse less or cache this aggressively
        cpt = ASComponent(sw.data)
        return render_template(
            'software/sw_details.html',
            AppStream=AppStream,
            screenshot_get_orig_image_url=screenshot_get_orig_image_url,
            ComponentKind=AppStream.ComponentKind,
            sw=sw,
            cpt=cpt,
            component_id=cid,
            packages_map=packages_map,
        )
