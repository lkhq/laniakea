# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
source_root = os.path.normpath(os.path.join(os.path.dirname(thisfile), '..'))
sys.path.append(os.path.normpath(os.path.join(source_root, 'src')))


pytest_plugins = ("tests.plugins.pytest_podman",)


__all__ = ['source_root',
           'pytest_plugins']
