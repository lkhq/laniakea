# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, render_template

from laniakea.db import Job, JobResult, ImageFormat, ImageBuildRecipe, session_scope

from ..utils import humanized_timediff

osimages = Blueprint('osimages', __name__, url_prefix='/osimages')


def last_jobs_for_recipe(session, recipe):
    return session.query(Job).filter(Job.trigger == recipe.uuid).order_by(Job.time_created.desc()).slice(0, 4).all()


@osimages.route('/')
def index():
    with session_scope() as session:
        recipes = session.query(ImageBuildRecipe).all()

        return render_template(
            'osimages/index.html',
            session=session,
            last_jobs_for_recipe=last_jobs_for_recipe,
            humanized_timediff=humanized_timediff,
            ImageFormat=ImageFormat,
            JobResult=JobResult,
            recipes=recipes,
        )
