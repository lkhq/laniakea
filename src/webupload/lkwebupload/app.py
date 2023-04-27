# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil
import logging as log
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

import jinja2
from flask import Flask

import laniakea.typing as T
from laniakea import LocalConfig

from .config import INSTANCE_FOLDER_PATH, DebugConfig, DefaultConfig

# For import *
__all__ = ['create_app']


thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
app_root_dir = os.path.normpath(os.path.join(os.path.dirname(thisfile), '..'))


@dataclass
class BaseDataCache:
    """Some data that we cache on startup, for very low overhead per single upload."""

    upload_chunk_size: int  # chunk size for uploads to be written to disk
    master_user: str  # Laniakea system user name
    incoming_dir: T.PathUnion  # path to incoming root directory
    repo_names: T.Set[str]  # set of repository+suite names that we accept uploads for

    def __init__(self, chunk_size: int):
        self.upload_chunk_size = chunk_size
        self.repo_names = set()


gdata: T.Optional[BaseDataCache] = None


def create_app(config=None, app_name=None):
    if app_name is None:
        app_name = DefaultConfig.PROJECT

    app = Flask(
        app_name, template_folder='templates', instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True
    )
    configure_app(app, config)

    configure_blueprints(app)
    configure_logging(app)

    return app


def configure_app(app, config=None):
    """
    Load app configuration - local production config takes
    precedence over others.
    """
    import tomlkit

    from laniakea import get_config_file
    from laniakea.db import ArchiveRepoSuiteSettings, session_scope

    global gdata

    if app.debug:
        app.config.from_object(DebugConfig)
    else:
        app.config.from_object(DefaultConfig)
    app.config.from_pyfile('config.cfg', silent=True)

    if config:
        app.config.from_object(config)

    template_dir = os.path.join(INSTANCE_FOLDER_PATH, 'templates')
    if not os.path.isdir(template_dir):
        template_dir = os.path.join(app_root_dir, 'templates')
    app.jinja_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(template_dir)])
    app.static_folder = os.path.join(template_dir, 'static')

    # cache some data we will need
    lconf = LocalConfig()
    rc_fname = get_config_file('rubicon.toml')
    rcdata = {}
    if rc_fname and os.path.isfile(rc_fname):
        with open(rc_fname) as f:
            rcdata = tomlkit.load(f)

    gdata = BaseDataCache(app.config['UPLOAD_CHUNK_SIZE'])
    gdata.master_user = lconf.master_user_name
    gdata.incoming_dir = rcdata.get('IncomingDir', lconf.upload_incoming_dir)

    with session_scope() as session:
        for rss in session.query(ArchiveRepoSuiteSettings).filter(ArchiveRepoSuiteSettings.accept_uploads.is_(True)):
            gdata.repo_names.add(str(rss.repo.name))
    for repo_name in gdata.repo_names:
        repo_incoming_dir = os.path.join(gdata.incoming_dir, repo_name)
        if not os.path.isdir(repo_incoming_dir):
            os.makedirs(repo_incoming_dir, exist_ok=True)
        shutil.chown(repo_incoming_dir, group=gdata.master_user)
        os.chmod(repo_incoming_dir, 0o775)


def configure_blueprints(app):
    """
    Configure blueprints
    """

    from .upload import upload

    blueprints = [upload]

    for bp in blueprints:
        app.register_blueprint(bp)


def configure_logging(app):
    """
    Configure file(info) and email(error) logging.
    """

    if app.debug or app.testing:
        # Skip debug and test mode. Just check standard output.
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
