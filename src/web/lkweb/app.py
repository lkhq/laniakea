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

from flask import Flask, render_template
from .config import DefaultConfig, INSTANCE_FOLDER_PATH


# For import *
__all__ = ['create_app']


def create_app(config=None, app_name=None):
    if app_name is None:
        app_name = DefaultConfig.PROJECT

    app = Flask(app_name, template_folder='templates', instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)
    configure_app(app, config)
    configure_blueprints(app)
    configure_logging(app)
    configure_error_handlers(app)
    configure_cli(app)

    return app


def configure_app(app, config=None):
    '''
    Load app configuration - local production config takes
    precedence over others.
    '''

    app.config.from_object(DefaultConfig)
    app.config.from_pyfile('lkweb.cfg', silent=True)

    if config:
        app.config.from_object(config)


def configure_blueprints(app):
    '''
    Configure blueprints
    '''

    from .api import api
    from .overview import overview
    from .migrations import migrations
    from .synchronization import synchronization
    from .jobs import jobs
    from .osimages import osimages
    from .depcheck import depcheck

    blueprints = [api,
                  migrations,
                  overview,
                  synchronization,
                  jobs,
                  osimages,
                  depcheck]

    for bp in blueprints:
        app.register_blueprint(bp)


def configure_logging(app):
    '''
    Configure file(info) and email(error) logging.
    '''

    if app.debug or app.testing:
        # Skip debug and test mode. Just check standard output.
        return

    import logging
    import os
    from logging.handlers import SMTPHandler

    # Set info level on logger, which might be overwritten by handers.
    # Suppress DEBUG messages.
    app.logger.setLevel(logging.INFO)

    info_log = os.path.join(app.config['LOG_FOLDER'], 'info.log')
    info_file_handler = logging.handlers.RotatingFileHandler(info_log, maxBytes=100000, backupCount=10)
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')
    )
    app.logger.addHandler(info_file_handler)

    # Testing
    # app.logger.info("testing info.")
    # app.logger.warn("testing warn.")
    # app.logger.error("testing error.")

    mail_handler = SMTPHandler(app.config['MAIL_SERVER'],
                               app.config['MAIL_USERNAME'],
                               app.config['ADMINS'],
                               'Error in Laniakea Web',
                               (app.config['MAIL_USERNAME'],
                                app.config['MAIL_PASSWORD']))
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')
    )
    app.logger.addHandler(mail_handler)


def configure_error_handlers(app):

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404


def configure_cli(app):

    @app.cli.command()
    def test():
        print('Hello World!')
