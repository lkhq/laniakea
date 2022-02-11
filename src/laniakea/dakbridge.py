# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import List

from laniakea.git import Git
from laniakea.utils import listify
from laniakea.logging import log, get_verbose
from laniakea.localconfig import LocalConfig, ExternalToolsUrls


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

        out, err, ret = run_command(cmd, input=input_data, capture_output=not get_verbose())
        out = out if out else ''
        err = err if err else ''
        if check and ret != 0:
            raise Exception('Failed to run dak: {}\n{}'.format(out, err))
        return ret, out + err

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

    def import_package_files(
        self, suite: str, component: str, fnames: List[str], ignore_signature: bool = False, add_overrides: bool = True
    ) -> bool:

        # run dak import command.
        args = ['import']
        if ignore_signature:
            args.append('-s')
        if add_overrides:
            args.append('-a')

        args.append(suite)
        args.append(component)
        args.extend(fnames)

        ret, out = self._run_dak(args, check=False)

        if ret != 0:
            raise Exception('Unable to import package files \'{}\': {}'.format(' '.join(fnames), out))

        log.info(
            'Imported \'{}\' into \'{}/{}\'.'.format(' '.join([os.path.basename(f) for f in fnames]), suite, component)
        )
        return True

    def package_is_removable(self, package_name: str, suite_name: str) -> bool:
        '''Check if a package can be removed without breaking reverse dependencies.'''

        log.debug('Testing package \'{}\' removal from \'{}\''.format(package_name, suite_name))

        # simulate package removal
        args = ['rm', '-R', '-m', 'RID: Removed from Debian', '-C', 'janitor@dak', '-n', '-s', suite_name, package_name]

        ret, out = self._run_dak(args, check=False)

        if ret != 0:
            raise Exception(
                'Unable to check if package \'{}\' is removable from \'{}\': {}'.format(package_name, suite_name, out)
            )
        return 'No dependency problem found.' in out

    def remove_package(self, package_name: str, suite_name: str) -> bool:
        '''Remove a package from a specified suite.'''

        log.info('Removing \'{}\' from \'{}\''.format(package_name, suite_name))

        # actually remove a package
        args = ['rm', '-m', 'RID: Removed from Debian', '-C', 'janitor@dak', '-s', suite_name, package_name]

        ret, out = self._run_dak(args, 'y\n', check=False)

        if ret != 0:
            raise Exception('Unable to remove package \'{}\' from \'{}\': {}'.format(package_name, suite_name, out))

        return True
