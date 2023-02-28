# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil

import tomlkit

import laniakea.typing as T
from laniakea.localconfig import get_config_file


class SchedulerConfig:
    """Configuration for the maintenance scheduler daemon."""

    instance = None

    class __SchedulerConfig:
        def __init__(self, fname=None):
            if not fname:
                fname = get_config_file('scheduler.toml')
            self.fname = fname

            cdata = {}
            if fname and os.path.isfile(fname):
                with open(fname) as toml_file:
                    cdata = tomlkit.load(toml_file)

            cintervals = cdata.get('Intervals', {})
            self._intervals_min = {}

            # run Rubicon every 15min by default
            self._intervals_min['rubicon'] = cintervals.get('rubicon', 15)

            # publish repos all 4h by default
            self._intervals_min['publish-repos'] = cintervals.get('publish-repos', 4 * 60)

            # expire old data in repos every 3 days by default
            self._intervals_min['expire-repos'] = cintervals.get('expire-repos', 3 * 24 * 60)

            # migrate packages all 6h by default
            self._intervals_min['spears-migrate'] = cintervals.get('spears-migrate', 6 * 60)

            # check the archive for dependency issues every 3h
            self._intervals_min['debcheck'] = cintervals.get('debcheck', 3 * 60)

            # check the archive for dependency issues every 12h
            self._intervals_min['synchrotron-autosync'] = cintervals.get('synchrotron-autosync', 12 * 60)

            # find executables
            my_dir = os.path.dirname(os.path.realpath(__file__))
            self._lk_archive_exe = os.path.normpath(os.path.join(my_dir, '..', 'lkarchive', 'lk-archive.py'))
            if not os.path.isfile(self._lk_archive_exe):
                self._lk_archive_exe = shutil.which('lk-archive')
            if not self._lk_archive_exe:
                raise ValueError('Unable to find the `lk-archive` binary. Check your Laniakea installation!')

            self._rubicon_exe = os.path.normpath(os.path.join(my_dir, '..', 'rubicon', 'rubicon'))
            if not os.path.isfile(self._rubicon_exe):
                self._rubicon_exe = shutil.which('rubicon')
            if not self._rubicon_exe:
                raise ValueError('Unable to find the `rubicon` binary. Check your Laniakea installation!')

            self._spears_exe = os.path.normpath(os.path.join(my_dir, '..', 'spears', 'spears'))
            if not self._spears_exe:
                raise ValueError('Unable to find the `spears` binary. Check your Laniakea installation!')

            self._debcheck_exe = os.path.normpath(os.path.join(my_dir, '..', 'debcheck', 'debcheck'))
            if not self._debcheck_exe:
                raise ValueError('Unable to find the `debcheck` binary. Check your Laniakea installation!')

            self._synchrotron_exe = os.path.normpath(os.path.join(my_dir, '..', 'synchrotron', 'synchrotron'))
            if not os.path.isfile(self._synchrotron_exe):
                self._synchrotron_exe = shutil.which('synchrotron')
            if not self._synchrotron_exe:
                raise ValueError('Unable to find the `synchrotron` binary. Check your Laniakea installation!')

        @property
        def lk_archive_exe(self) -> T.PathUnion:
            """Executable path for lk-archive"""
            return self._lk_archive_exe

        @property
        def rubicon_exe(self) -> T.PathUnion:
            """Executable path for rubicon"""
            return self._rubicon_exe

        @property
        def spears_exe(self) -> T.PathUnion:
            """Executable path for spears"""
            return self._spears_exe

        @property
        def debcheck_exe(self) -> T.PathUnion:
            """Executable path for debcheck"""
            return self._debcheck_exe

        @property
        def synchrotron_exe(self) -> T.PathUnion:
            """Executable path for synchrotron"""
            return self._synchrotron_exe

        @property
        def intervals_min(self) -> T.Dict[str, T.Optional[int]]:
            """Defined intervals to run the respective jobs at"""
            return self._intervals_min

    def __init__(self, fname=None):
        if not SchedulerConfig.instance:
            SchedulerConfig.instance = SchedulerConfig.__SchedulerConfig(fname)

    def __getattr__(self, name):
        return getattr(self.instance, name)
