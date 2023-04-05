# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+
import os.path

import laniakea.typing as T
from laniakea.utils import run_command


class Git:
    '''
    Interface with Git (currently the cli tool)
    to perform some basic operations on Git repositories.
    '''

    def __init__(self, location: T.Optional[T.PathUnion] = None):
        self._git_exe = 'git'
        self._location = location

    @property
    def location(self) -> str:
        '''
        The on-disk location of this Git repository.
        '''
        return self._location

    @location.setter
    def location(self, path):
        self._location = path

    def _run_git(self, command, args, clone_dir=None, throw_error=True):
        git_cmd = [self._git_exe]
        if command == 'clone':
            git_cmd.append(command)
        elif clone_dir:
            git_cmd.extend(['-C', clone_dir, command])
        if args:
            git_cmd.extend(args)

        out, err, ret = run_command(git_cmd)
        if ret == 0:
            return True
        elif throw_error:
            raise Exception('Failed to run Git ({}): {}\n{}'.format(' '.join(git_cmd), out, err))

    def clone(self, repo_url: str):
        """Clone a Git repository to target location."""
        if not self._location:
            raise Exception('Git clone destination is not set.')
        return self._run_git('clone', [repo_url, self._location])

    def pull(self, origin: T.Optional[str] = None, branch: T.Optional[str] = None):
        """Pull from an existing repository."""
        args = []
        if origin and branch:
            args = [origin, branch]

        return self._run_git('pull', args, self._location)

    def clone_or_pull(self, repo_url: str, *, origin: T.Optional[str] = None, branch: T.Optional[str] = None):
        """Clone repository if target location does not exist, pull otherwise."""
        if not self._location:
            raise Exception('Git clone destination is not set.')

        if not os.path.exists(self._location) or len(os.listdir(self._location)) == 0:
            self.clone(repo_url)
        else:
            self.pull(origin, branch)
