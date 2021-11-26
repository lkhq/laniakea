# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys

__version__ = '0.1.0'

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
lk_py_directory = os.path.normpath(os.path.join(os.path.dirname(thisfile)))
sys.path.append(lk_py_directory)

from laniakea.db import LkModule
from laniakea.localconfig import LocalConfig, get_config_file

__all__ = ['LocalConfig', 'get_config_file', 'LkModule']
