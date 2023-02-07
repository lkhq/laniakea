# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

# Instance folder path
INSTANCE_FOLDER_PATH = '/var/lib/laniakea/webupload/'


class BaseConfig:
    PROJECT = 'Laniakea HTTP Upload Receiver'
    BUG_REPORT_URL = 'https://github.com/lkhq/laniakea/issues'

    # Get app root path, also can use flask.root_path.
    # ../../config.py
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    DEBUG = False
    TESTING = False

    # http://flask.pocoo.org/docs/quickstart/#sessions
    SECRET_KEY = 'secret key'

    LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')

    UPLOAD_CHUNK_SIZE = 4096


class DefaultConfig(BaseConfig):
    DEBUG = False


class DebugConfig(BaseConfig):
    DEBUG = True
