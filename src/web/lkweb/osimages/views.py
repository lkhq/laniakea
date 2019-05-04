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

from flask import Blueprint, render_template
from laniakea.db import session_scope, ImageBuildRecipe, ImageKind, Job, JobResult
from ..utils import humanized_timediff

osimages = Blueprint('osimages',
                     __name__,
                     url_prefix='/osimages')


def last_jobs_for_recipe(session, recipe):
    return session.query(Job) \
        .filter(Job.trigger == recipe.uuid) \
        .order_by(Job.time_created.desc()) \
        .slice(0, 4) \
        .all()


@osimages.route('/')
def index():
    with session_scope() as session:
        recipes = session.query(ImageBuildRecipe).all()

        return render_template('osimages/index.html',
                               session=session,
                               last_jobs_for_recipe=last_jobs_for_recipe,
                               humanized_timediff=humanized_timediff,
                               ImageKind=ImageKind,
                               JobResult=JobResult,
                               recipes=recipes)
