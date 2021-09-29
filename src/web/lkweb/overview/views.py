# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask import Blueprint, render_template


overview = Blueprint('overview', __name__)


@overview.route('/')
def index():
    return render_template('index.html')
