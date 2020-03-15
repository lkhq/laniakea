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

import yaml
from typing import Dict
from datetime import datetime
from laniakea.db import SpearsExcuse, SpearsOldBinaries


class ExcusesFile:
    '''
    Read the excuses.yml Britney output file as well as the Britney logfile
    and create SpearsExcuse structs to be added to the database from their data.
    '''

    def __init__(self, fname_excuses: str, fname_log: str, source: str, target: str):
        self._suite_source = source
        self._suite_target = target

        with open(fname_excuses, 'r') as f:
            self._excuses_data = yaml.safe_load(f)

        with open(fname_log) as f:
            self._log_data = [line.rstrip() for line in f]

    def _process_log_data(self):
        '''
        Generate a dictionary of packageName -> logExcerpt from
        the logfile.
        '''

        res = {}
        current_packages = []

        for line in self._log_data:
            # stop adding hinter information if we leave a block
            if not line:
                current_packages = []
                continue

            # simple migrations
            if line.startswith('trying:'):
                current_packages = [line[7:].strip()]

            # autohinter action
            if line.startswith('Trying easy from autohinter:'):
                pkgs_line = line[28:].strip()
                for pkgid in pkgs_line.split(' '):
                    parts = pkgid.split('/')
                    current_packages.append(parts[0])

            # ignore uninteresting entries
            if not current_packages:
                continue

            for pkg in current_packages:
                if pkg not in res:
                    res[pkg] = ''
                res[pkg] = res[pkg] + line + '\n'

        return res

    def get_excuses(self) -> Dict[str, SpearsExcuse]:

        res = {}

        # get log data
        loginfo = self._process_log_data()

        ysrc = self._excuses_data['sources']
        for entry in ysrc:
            excuse = SpearsExcuse()

            excuse.date = datetime.utcnow()
            excuse.suite_source = self._suite_source
            excuse.suite_target = self._suite_target

            excuse.source_package = str(entry['source'])
            excuse.is_candidate = bool(entry['is-candidate'])

            if 'maintainer' in entry:
                excuse.maintainer = str(entry['maintainer'])

            excuse.version_new = str(entry['new-version'])
            excuse.version_old = str(entry['old-version'])

            if 'policy_info' in entry:
                policy = entry['policy_info']
                if 'age' in policy:
                    excuse.age_current = int(policy['age']['current-age'])
                    excuse.age_required = int(policy['age']['age-requirement'])

            if 'missing-builds' in entry:
                ybuilds = entry['missing-builds']
                excuse.missing_archs_primary = list(ybuilds['on-architectures'])
                excuse.missing_archs_secondary = list(ybuilds['on-unimportant-architectures'])

            if 'old-binaries' in entry:
                obins = []
                for yver, ybins in entry['old-binaries'].items():
                    obin = SpearsOldBinaries()
                    obin.pkg_version = str(yver)
                    obin.binaries = list(ybins)
                    obins.append(obin)
                excuse.set_old_binaries(obins)

            if 'dependencies' in entry:
                ydeps = entry['dependencies']
                if 'migrate-after' in ydeps:
                    excuse.migrate_after = list(ydeps['migrate-after'])

                if 'blocked-by' in ydeps:
                    excuse.blocked_by = list(ydeps['blocked-by'])

            # other plaintext excuses
            if 'excuses' in entry:
                excuse.other = ''
                for n in entry['excuses']:
                    s = str(n)
                    if 'Cannot be tested by piuparts' not in s and 'but ignoring cruft, so nevermind' not in s:
                        excuse.other = excuse.other + s

            # add log information
            excuse.log_excerpt = loginfo.get(excuse.source_package)

            res[excuse.make_idname()] = excuse

        return res
