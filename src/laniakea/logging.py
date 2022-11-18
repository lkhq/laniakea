# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import logging as log
import datetime

__all__ = ['log', 'set_verbose', 'get_verbose']

import os

__verbose_logging = False

archive_log = log.getLogger('pkg_archive')  # special logger to log package archive changes

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


def configure_pkg_archive_logger():
    from laniakea.localconfig import LocalConfig

    lconf = LocalConfig()

    archive_log.setLevel(log.INFO)
    archive_log.propagate = False  # don't forward log messages to default logger

    date_today = datetime.date.today()
    archive_log_dir = os.path.join(lconf.log_root_dir, 'archive', date_today.strftime("%Y"))
    os.makedirs(archive_log_dir, exist_ok=True)

    fh = log.FileHandler(os.path.join(archive_log_dir, 'pkgarchive-w{}.log'.format(date_today.isocalendar().week)))
    formatter = log.Formatter('%(levelname).1s: %(asctime)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    fh.setFormatter(formatter)
    archive_log.handlers.clear()  # we don't want to log this to stdout
    archive_log.addHandler(fh)
