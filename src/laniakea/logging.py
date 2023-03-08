# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import logging as log
import datetime
import threading

__all__ = ['log', 'set_verbose', 'get_verbose', 'archive_log', 'configure_pkg_archive_logger']

import os

__verbose_logging = False
__archive_logger_enabled = False
_lock = threading.RLock()

archive_log = log.getLogger('pkg_archive')  # special logger to log package archive changes

log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')


def set_verbose(enabled):
    global __verbose_logging

    __verbose_logging = enabled

    if enabled:
        log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        log.getLogger().setLevel(log.DEBUG)
    else:
        log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')


def get_verbose():
    return __verbose_logging


def configure_pkg_archive_logger():
    from laniakea.localconfig import LocalConfig

    global __archive_logger_enabled

    # check if we're already configured
    if not archive_log.propagate:
        return

    with _lock:
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

        __archive_logger_enabled = True


#
# Global module configuration, to auto-reload it when using multiprocess
# or multithreading code.
#
set_verbose(__verbose_logging)
if __archive_logger_enabled:
    configure_pkg_archive_logger()
