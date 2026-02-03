# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import re
from typing import Dict
from datetime import datetime

import yaml

from laniakea.db import (
    SpearsExcuse,
    SourcePackage,
    SpearsOldBinaries,
    SpearsMigrationTask,
)


class ExcusesFile:
    '''
    Read the excuses.yml Britney output file as well as the Britney logfile
    and create SpearsExcuse objects to be added to the database from their data.
    '''

    def __init__(self, session, fname_excuses: str, fname_log: str, mtask: SpearsMigrationTask):
        self._session = session
        self._mtask = mtask
        self._suites_source = mtask.source_suites
        self._suite_target = mtask.target_suite

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
                pkgid = line[7:].strip()
                if pkgid.startswith('-'):
                    pkgid = pkgid[1:]
                if '/' in pkgid:
                    pkgid = pkgid.split('/', 2)[0]
                current_packages = [pkgid]

            # autohinter action
            if line.startswith('Trying easy from autohinter:'):
                pkgs_line = line[28:].strip()
                for pkgid in pkgs_line.split(' '):
                    if pkgid.startswith('-'):
                        pkgid = pkgid[1:]
                    if '/' in pkgid:
                        pkgid = pkgid.split('/', 2)[0]
                    current_packages.append(pkgid)

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

        other_reason_ignore_strings = (
            'Cannot be tested by piuparts',
            'but ignoring cruft, so nevermind',
            'Issues preventing migration:',
            'Additional info:',
            ' days old (needed ',
        )
        debian_buildd_link_re = r'<a href="https://buildd\.debian\.org/status/logs\.php\?arch=[^&]+&pkg=[^&]+&ver=[^"]+" target="_blank">([^<]+)</a>'  # noqa: E501

        # get log data
        loginfo = self._process_log_data()

        ysrc = self._excuses_data['sources']
        for entry in ysrc:
            excuse = SpearsExcuse()

            excuse.time_created = datetime.utcnow()
            excuse.migration_task = self._mtask

            spkg_name = str(entry['source'])
            excuse.version_new = str(entry['new-version'])
            excuse.version_old = str(entry['old-version'])

            spkg_version = excuse.version_new
            if not spkg_version or spkg_version == '-':
                # the package might be deleted, so we need to search for the *old* version instead
                spkg_version = excuse.version_old

            excuse.source_package = (
                self._session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == self._mtask.repo.id,
                    SourcePackage.name == spkg_name,
                    SourcePackage.version == spkg_version,
                )
                .one_or_none()
            )
            if not excuse.source_package:
                raise ValueError("Unable to find source package %s/%s!" % (spkg_name, spkg_version))

            excuse.is_candidate = bool(entry['is-candidate'])
            if 'maintainer' in entry:
                excuse.maintainer = str(entry['maintainer'])

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
                excuse.other = []
                for n in entry['excuses']:
                    s = str(n)
                    if not any(test in s for test in other_reason_ignore_strings):
                        if s.startswith('∙ ∙ '):
                            s = s[4:]
                        if 'buildd.debian.org' in s:
                            s = re.sub(debian_buildd_link_re, r'\1', s)
                        excuse.other.append(s)

            # add log information
            excuse.log_excerpt = loginfo.get(excuse.source_package.name)

            res[excuse.make_idname()] = excuse

        return res
