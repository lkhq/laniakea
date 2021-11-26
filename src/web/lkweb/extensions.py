# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from flask_login import LoginManager
from flask_caching import Cache

login_manager = LoginManager()

cache = Cache()
