# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from laniakea.utils import run_command


class Git:
    '''
    Interface with Git (currently the cli tool)
    to perform some basic operations on Git repositories.
    '''

    def __init__(self):
        self._git_exe = 'git'
        self._location = None

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

    def clone(self, repo_url):
        if not self._location:
            raise Exception('Git clone destination is not set.')
        return self._run_git('clone', [repo_url, self._location])

    def pull(self, origin=None, branch=None):
        args = []
        if origin and branch:
            args = [origin, branch]

        return self._run_git('pull', args, self._location)
