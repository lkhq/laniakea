# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import logging as log
from logging.handlers import RotatingFileHandler

import jinja2
from flask import Flask, render_template

from .api import rebar
from .config import INSTANCE_FOLDER_PATH, DebugConfig, DefaultConfig
from .extensions import cache

# For import *
__all__ = ['create_app']


thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
app_root_dir = os.path.normpath(os.path.join(os.path.dirname(thisfile), '..'))


def create_app(config=None, app_name=None):
    if app_name is None:
        app_name = DefaultConfig.PROJECT

    app = Flask(app_name, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)
    configure_app(app, config)
    cache.init_app(app)
    rebar.init_app(app)

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

    if app.debug:
        app.config.from_object(DebugConfig)
    else:
        app.config.from_object(DefaultConfig)
    app.config.from_pyfile('config.cfg', silent=True)

    if config:
        app.config.from_object(config)

    template_theme_dir = os.path.join(INSTANCE_FOLDER_PATH, 'templates', app.config['THEME'])
    if not os.path.isdir(template_theme_dir):
        template_theme_dir = os.path.join(app_root_dir, 'templates', app.config['THEME'])
    template_default_dir = os.path.join(app_root_dir, 'templates', 'default')

    app.jinja_loader = jinja2.ChoiceLoader(
        [jinja2.FileSystemLoader(template_theme_dir), jinja2.FileSystemLoader(template_default_dir)]
    )
    app.static_folder = os.path.join(template_theme_dir, 'static')


def configure_blueprints(app):
    '''
    Configure blueprints
    '''

    from .portal import portal
    from .packages import packages
    from .software import software

    blueprints = [portal, packages, software]

    for bp in blueprints:
        app.register_blueprint(bp)


def configure_logging(app):
    '''
    Configure file(info) and email(error) logging.
    '''

    if app.debug or app.testing:
        # log everything
        return

    # Set warning level on logger, which might be overwritten by handers.
    # Suppress DEBUG messages.
    app.logger.setLevel(log.WARNING)

    os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
    info_log = os.path.join(app.config['LOG_FOLDER'], 'info.log')
    info_file_handler = RotatingFileHandler(info_log, maxBytes=100000, backupCount=10)
    info_file_handler.setLevel(log.INFO)
    info_file_handler.setFormatter(log.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.addHandler(info_file_handler)

    # supress GET etc. messages from Werkzeug
    wlog = log.getLogger('werkzeug')
    wlog.setLevel(log.ERROR)

    # Testing
    # app.logger.info("testing info.")
    # app.logger.warn("testing warn.")
    # app.logger.error("testing error.")


def configure_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def page_not_found(error):
        return render_template("errors/500.html"), 500


def configure_cli(app):
    @app.cli.command()
    def test():
        print('Hello World!')
