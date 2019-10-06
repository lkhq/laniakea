# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
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
import subprocess
import yaml
from datetime import datetime
from laniakea.localconfig import LocalConfig
from laniakea.repository import Repository
from laniakea.db import DebcheckIssue, PackageType, PackageIssue, PackageConflict
from laniakea.logging import log


class Debcheck:
    '''
    Analyze the archive's dependency chain.
    '''

    def __init__(self, repo_entity):
        lconf = LocalConfig()
        self._repo = Repository(lconf.archive_root_dir, 'master', entity=repo_entity)
        self._repo_entity = repo_entity
        self._repo.set_trusted(True)

    def _execute_dose(self, dose_exe, args, files=[]):

        yaml_data = ''
        cmd = [dose_exe]
        cmd.extend(args)
        cmd.extend(files)

        pipe = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        while True:
            line = pipe.stdout.readline()
            if line == '' and pipe.poll() is not None:
                break
            if line:
                yaml_data += line

        if not yaml_data.startswith('output-version'):
            # the output is weird, assume an error
            return False, yaml_data + '\n' + pipe.stderr.read()

        return True, yaml_data

    def _get_full_index_info(self, suite, arch, sources=False):
        '''
        Get a list of index files for the specific suite and architecture,
        for all components, as well as all the suites it depends on.

        The actual indices belonging to the suite are added as "foreground" (fg), the
        ones of the dependencies are added as "background" (bg).
        '''

        res = {'fg': [], 'bg': []}
        bin_arch = suite.primary_architecture

        for component in suite.components:
            if sources:
                fname = self._repo.index_file(suite, os.path.join(component.name, 'source', 'Sources.xz'))
                if fname:
                    res['fg'].append(fname)

                fname = self._repo.index_file(suite, os.path.join(component.name, 'binary-{}'.format(arch.name), 'Packages.xz'))
                if fname:
                    res['bg'].append(fname)
            else:
                fname = self._repo.index_file(suite, os.path.join(component.name, 'binary-{}'.format(arch.name), 'Packages.xz'))
                if fname:
                    res['fg'].append(fname)

            if arch.name == 'all':
                fname = self._repo.index_file(suite, os.path.join(component.name, 'binary-{}'.format(bin_arch.name), 'Packages.xz'))
                if fname:
                    res['bg'].append(fname)

        # add base suite packages to the background
        if suite.parent:
            parent_indices = self._get_full_index_info(suite.parent, arch, sources)
            res['bg'].extend(parent_indices['bg'])
            res['bg'].extend(parent_indices['fg'])

        return res

    def _generate_build_depcheck_yaml(self, suite):
        '''
        Get Dose YAML data for build dependency issues in the selected suite.
        '''

        arch_issue_map = {}
        for arch in suite.architectures:
            # fetch source-package-centric index list
            indices = self._get_full_index_info(suite, arch, True)
            if not indices['fg']:
                if arch.name == 'all':
                    continue
                raise Exception('Unable to get any indices for {}/{} to check for dependency issues.'.format(suite.name, arch.name))

            dose_args = ['--quiet',
                         '--latest=1',
                         '-e',
                         '-f',
                         '--summary',
                         '--deb-emulate-sbuild',
                         '--deb-native-arch={}'.format(suite.primary_architecture.name if arch == 'all' else arch.name)]

            # run builddepcheck
            success, data = self._execute_dose('dose-builddebcheck', dose_args, indices['bg'] + indices['fg'])
            if not success:
                raise Exception('Unable to run Dose for {}/{}: {}'.format(suite.name, arch.name, data))
            arch_issue_map[arch.name] = data

        return arch_issue_map

    def _generate_depcheck_yaml(self, suite):
        '''
        Get Dose YAML data for build installability issues in the selected suite.
        '''

        arch_issue_map = {}
        for arch in suite.architectures:
            # fetch binary-package index list
            indices = self._get_full_index_info(suite, arch, False)
            if not indices['fg']:
                if arch.name == 'all':
                    continue
                raise Exception('Unable to get any indices for {}/{} to check for dependency issues.'.format(suite.name, arch.name))

            dose_args = ['--quiet',
                         '--latest=1',
                         '-e',
                         '-f',
                         '--summary',
                         '--deb-native-arch={}'.format(suite.primary_architecture.name if arch == 'all' else arch.name)]

            # run depcheck
            indices_args = []
            for f in indices['bg']:
                indices_args.append('--bg={}'.format(f))
            for f in indices['fg']:
                indices_args.append('--fg={}'.format(f))
            success, data = self._execute_dose('dose-debcheck', dose_args, indices_args)
            if not success:
                log.error('Dose debcheck command failed: ' + ' '.join(dose_args) + ' ' + ' '.join(indices_args) + '\n' + data)
                raise Exception('Unable to run Dose for {}/{}: {}'.format(suite.name, arch.name, data))

            arch_issue_map[arch.name] = data

        return arch_issue_map

    def _dose_yaml_to_issues(self, yaml_data, suite, arch_name):

        def set_basic_package_info(v, entry):
            if 'type' in entry and entry['type'] == "src":
                v.package_type = PackageType.SOURCE
            else:
                v.package_type = PackageType.BINARY

            v.package_name = str(entry['package'])
            v.package_version = str(entry['version'])
            v.architecture = str(entry['architecture']).split(',')

        res = []
        yroot = yaml.safe_load(yaml_data)
        report = yroot['report']
        arch_is_all = arch_name == 'all'

        # if the report is empty, we have no issues to generate and can quit
        if not report:
            return res

        for entry in report:
            if not arch_is_all:
                # we ignore entries from "all" unless we are explicitly reading information
                # for that fake architecture.
                if entry['architecture'] == 'all':
                    continue

            issue = DebcheckIssue()
            issue.repo = self._repo_entity
            issue.time = datetime.utcnow()
            issue.suite = suite
            issue.missing = []
            issue.conflicts = []

            set_basic_package_info(issue, entry)

            reasons = entry['reasons']
            for reason in reasons:
                if 'missing' in reason:
                    # we have a missing package issue
                    ymissing = reason['missing']['pkg']
                    pkgissue = PackageIssue()
                    set_basic_package_info(pkgissue, ymissing)
                    pkgissue.unsat_dependency = ymissing['unsat-dependency']

                    issue.missing.append(pkgissue)
                elif 'conflict' in reason:
                    # we have a conflict in the dependency chain
                    yconflict = reason['conflict']
                    conflict = PackageConflict()
                    conflict.pkg1 = PackageIssue()
                    conflict.pkg2 = PackageIssue()
                    conflict.depchain1 = []
                    conflict.depchain2 = []

                    set_basic_package_info(conflict.pkg1, yconflict['pkg1'])
                    if 'unsat-conflict' in yconflict['pkg1']:
                        conflict.pkg1.unsat_conflict = yconflict['pkg1']['unsat-conflict']

                    set_basic_package_info(conflict.pkg2, yconflict['pkg2'])
                    if 'unsat-conflict' in yconflict['pkg2']:
                        conflict.pkg2.unsat_conflict = yconflict['pkg2']['unsat-conflict']

                    # parse the depchain
                    if 'depchain1' in yconflict:
                        for ypkg in yconflict['depchain1'][0]['depchain']:
                            pkgissue = PackageIssue()
                            set_basic_package_info(pkgissue, ypkg)
                            pkgissue.depends = ypkg.get('depends')
                            conflict.depchain1.append(pkgissue)

                    if 'depchain2' in yconflict:
                        for ypkg in yconflict['depchain2'][0]['depchain']:
                            pkgissue = PackageIssue()
                            set_basic_package_info(pkgissue, ypkg)
                            pkgissue.depends = ypkg.get('depends')
                            conflict.depchain2.append(pkgissue)

                    issue.conflicts.append(conflict)
                else:
                    raise Exception('Found unknown dependency issue: ' + str(reason))

            res.append(issue)

        return res

    def build_depcheck_issues(self, suite):
        ''' Get a list of build-dependency issues affecting the suite '''

        issues = []
        issues_yaml = self._generate_build_depcheck_yaml(suite)
        for arch_name, yaml_data in issues_yaml.items():
            issues.extend(self._dose_yaml_to_issues(yaml_data, suite, arch_name))

        return issues

    def depcheck_issues(self, suite):
        ''' Get a list of dependency issues affecting the suite '''

        issues = []
        issues_yaml = self._generate_depcheck_yaml(suite)
        for arch_name, yaml_data in issues_yaml.items():
            issues.extend(self._dose_yaml_to_issues(yaml_data, suite, arch_name))

        return issues
