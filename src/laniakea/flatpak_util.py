# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import shutil
from laniakea import LocalConfig
from laniakea.db import FlatpakRepository
from laniakea.utils import safe_run_forwarded


class FlatpakUtil:
    '''
    Interface with the Flatpak CLI tools to perform verious administrative
    actions on repositories.
    '''

    def __init__(self):
        self._flatpak_exe = shutil.which('flatpak')
        self._ostree_exe = shutil.which('ostree')
        self._lconf = LocalConfig()

        if not self._flatpak_exe:
            raise Exception('Unable to find the "flatpak" binary, can not modify Flatpak repositories.')
        if not self._ostree_exe:
            raise Exception('Unable to find the "ostree" binary, can not modify Flatpak repositories.')

    def _run_ostree(self, args):
        ''' Run an OSTree CLI command '''
        cmd = [self._ostree_exe]
        cmd.extend(args)
        return safe_run_forwarded(cmd)

    def _run_flatpak(self, args):
        ''' Run a Flatpak CLI command '''
        cmd = [self._flatpak_exe]
        cmd.extend(args)
        return safe_run_forwarded(cmd)

    def init_repo(self, repo: FlatpakRepository, repo_path: str):
        ''' Initialize a new, empty Flatpak repository '''

        ost_args = ['init',
                    '--mode', 'archive-z2',
                    '--repo', repo_path]
        self._run_ostree(ost_args)

        fp_args = ['build-update-repo',
                   '--title', repo.title,
                   '--default-branch', repo.default_branch,
                   '--collection-id', repo.collection_id,
                   '--gpg-sign', repo.gpg_key_id,
                   '--gpg-homedir', self._lconf.secret_gpg_home_dir]
        if repo.comment:
            fp_args.extend(['--comment', repo.comment])
        if repo.description:
            fp_args.extend(['--description', repo.description])
        if repo.url_homepage:
            fp_args.extend(['--homepage', repo.url_homepage])
        if repo.url_icon:
            fp_args.extend(['--icon', repo.url_icon])

        fp_args.append(repo_path)
        self._run_flatpak(fp_args)
