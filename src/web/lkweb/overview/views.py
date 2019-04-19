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

from uuid import uuid4

from flask import Blueprint, render_template, current_app, request, flash, \
    url_for, redirect, session, abort
from flask_login import login_required, login_user, current_user, logout_user, \
    confirm_login, login_fresh


overview = Blueprint('overview', __name__)


@overview.route('/')
def index():
    return render_template('index.html')
