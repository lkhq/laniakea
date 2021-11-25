# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

from laniakea.git import Git
from laniakea.localconfig import ExternalToolsUrls, LocalConfig
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
