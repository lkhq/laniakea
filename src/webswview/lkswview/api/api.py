# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask_rebar import Rebar, SwaggerV3Generator
from marshmallow import Schema, fields

rebar = Rebar()

# All handler URL rules will be prefixed by '/v1'
registry = rebar.create_handler_registry(
    prefix='/api/v1',
    spec_path='/apidocs',
    swagger_ui_path='/apidocs/ui',
    swagger_generator=SwaggerV3Generator(title='Laniakea SW API'),
)


class TodoSchema(Schema):
    id = fields.Integer()
    complete = fields.Boolean()
    description = fields.String()


# This schema will validate the incoming request's query string
class GetTodosQueryStringSchema(Schema):
    complete = fields.Boolean()


# This schema will marshal the outgoing response
class GetTodosResponseSchema(Schema):
    data = fields.Nested(TodoSchema, many=True)


@registry.handles(
    rule='/todos',
    method='GET',
    query_string_schema=GetTodosQueryStringSchema(),
    response_body_schema=GetTodosResponseSchema(),  # for versions <= 1.7.0, use marshal_schema
)
def get_todos():
    """
    This docstring will be rendered as the operation's description in
    the auto-generated OpenAPI specification.
    """

    # The response will be marshaled by `marshal_schema`
    return {'data': []}
