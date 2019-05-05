# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
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

import logging as log


__all__ = ['log',
           'set_verbose',
           'get_verbose']


__verbose_logging = False


if not __verbose_logging:
    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')


def set_verbose(enabled):
    from lknative import logging_set_verbose
    global __verbose_logging

    __verbose_logging = enabled
    logging_set_verbose(enabled)

    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    if enabled:
        log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        log.getLogger().setLevel(log.DEBUG)


def get_verbose():
    global __verbose_logging
    return __verbose_logging
