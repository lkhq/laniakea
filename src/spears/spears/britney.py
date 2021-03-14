# Copyright (C) 2018-2020 Matthias Klumpp <matthias@tenstral.net>
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

import os
from laniakea.localconfig import LocalConfig, ExternalToolsUrls
from laniakea.git import Git
from laniakea.logging import get_verbose


class Britney:
    '''
    Interface to Debian's Archive Migrator (Britney2)
    '''

    def __init__(self):
        lconf = LocalConfig()

        self._britney_dir = os.path.join(lconf.workspace, 'dist', 'britney2')
        self._britney_exe = os.path.join(self._britney_dir, 'britney.py')

    def update_dist(self):
        ext_urls = ExternalToolsUrls()

        git = Git()
        git.location = self._britney_dir
        if os.path.isdir(os.path.join(self._britney_dir, '.git')):
            git.pull()
        else:
            os.makedirs(self._britney_dir, exist_ok=True)
            git.clone(ext_urls.britney_git_repository)

    def run(self, wdir, config_fname, args: list[str] = None):
        from laniakea.utils import run_forwarded

        if not args:
            args = []

        cmd = [self._britney_exe]
        cmd.extend(['-c', config_fname])
        cmd.extend(args)

        out, ret = run_forwarded(cmd, cwd=wdir, print_output=get_verbose())
        if ret != 0:
            raise Exception('Britney run failed: {}'.format(out))

        return out
