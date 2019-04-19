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

from flask import Blueprint, request, jsonify
from flask_login import login_user, current_user, logout_user
from flask_restful import Api, Resource

api = Blueprint('api', __name__, url_prefix='/api')
api_wrap = Api(api)


class TodoItem(Resource):
    def get(self, id):
        return {'task': 'Say "Hello, World!"'}

api_wrap.add_resource(TodoItem, '/todos/<int:id>')
