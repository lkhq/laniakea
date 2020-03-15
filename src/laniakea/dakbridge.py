# -*- coding: utf-8 -*-
#
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
from laniakea.logging import log, get_verbose
from laniakea.utils import listify


class DakBridge:
    '''
    Call commands on the Debian Archive Kit (dak)
    CLI utility.
    '''

    def __init__(self):
        lconf = LocalConfig()

        self._dak_dist_dir = os.path.join(lconf.workspace, 'dist', 'dak')
        self._dak_exe = os.path.join(self._dak_dist_dir, 'dak', 'dak.py')

    def update_dak(self):
        ext_urls = ExternalToolsUrls()

        git = Git()
        git.location = self._dak_dist_dir
        if os.path.isdir(os.path.join(self._dak_dist_dir, '.git')):
            git.pull()
        else:
            os.makedirs(self._dak_dist_dir, exist_ok=True)
            git.clone(ext_urls.dak_git_repository)

    def _run_dak(self, args, input_data=None, check=True):
        from laniakea.utils import run_command

        cmd = [self._dak_exe]
        cmd.extend(args)

        out, err, ret = run_command(cmd,
                                    input=input_data,
                                    capture_output=not get_verbose())
        if check and ret != 0:
            raise Exception('Failed to run dak: {}\n{}'.format(out if out else '', err if err else ''))
        return ret, out

    def run(self, command):
        '''
        Run dak with the given commands.
        '''
        command = listify(command)

        return self._run_dak(command)

    def set_suite_to_britney_result(self, suite_name: str, heidi_file: str) -> bool:
        '''
        Import a Britney result (HeidiResult file) into the dak database.
        This will *override* all existing package information in the target suite.
        Use this command with great care!
        '''

        # do some sanity checks
        if not os.path.isfile(heidi_file):
            log.warning('Britney result not imported: File "{}" does not exist.'.format(heidi_file))
            return False

        # an empty file might cause us to delete the whole repository contents.
        # this is a safeguard against that.
        heidi_data = None
        with open(heidi_file, 'r') as f:
            heidi_data = f.read().strip()
        if not heidi_data:
            log.warning('Stopped Britney result import: File "{}" is empty.'.format(heidi_file))
            return True

        log.info('Importing britney result from {}'.format(heidi_file))

        # run dak control-suite command.
        args = ['control-suite']
        args.extend(['--set', suite_name, '--britney'])
        ret, out = self._run_dak(args, input_data=heidi_data, check=False)

        if ret != 0:
            raise Exception('Unable apply Britney result to "{}": {}'.format(suite_name, out))

        log.info('Updated packages in "{}" based on Britney result.'.format(suite_name))

        return True
