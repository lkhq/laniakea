# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import logging as log

__all__ = ['log', 'set_verbose', 'get_verbose']


__verbose_logging = False


if not __verbose_logging:
    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')


def set_verbose(enabled):
    global __verbose_logging

    __verbose_logging = enabled

    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    if enabled:
        log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        log.getLogger().setLevel(log.DEBUG)


def get_verbose():
    return __verbose_logging
