# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import Dict, List

from laniakea.db import SpearsHint, ChangesUrgency
from laniakea.logging import log


class BritneyConfig:
    '''
    Defines a Britney2 configuration file.
    '''

    def __init__(self, britney_dir: str):

        self._contents: list[str] = []
        self._hint_contents: list[str] = []

        self._paths_set = False
        self._components_set = False
        self._archs_set = False
        self._broken_archs_set = False
        self._delays_set = False
        self._new_archs_set = False
        self._partial_source = False

        self._base_dir = britney_dir

        # add basic settings
        self._contents.append(
            '# Configuration file for Britney\n# This file is managed by Laniakea.Spears - DO NOT EDIT IT MANUALLY!\n'
        )

        # output
        self._contents.append('NONINST_STATUS      = output/target/non-installable-status')
        self._contents.append('EXCUSES_OUTPUT      = output/target/excuses.html')
        self._contents.append('EXCUSES_YAML_OUTPUT = output/target/excuses.yaml')
        self._contents.append('UPGRADE_OUTPUT      = output/target/output.txt')
        self._contents.append('HEIDI_OUTPUT        = output/target/HeidiResult')
        self._contents.append('HEIDI_DELTA_OUTPUT  = output/target/HeidiResultDelta')

        # external policy/constraints/faux-packages information that
        # (presumably) rarely changes.  Examples include "constraints".
        self._contents.append('STATIC_INPUT_DIR = input/')
        self._contents.append('HINTSDIR         = input/hints')

        # directory for input files that Britney will update herself
        # (e.g. aging information) or will need regular updates
        # (e.g. urgency information).
        self._contents.append('STATE_DIR        = state/')

        # allow Laniakea to set all hint types
        self._contents.append('HINTS_LANIAKEA   = ALL')

        # support for old libraries in testing (smooth update)
        # use ALL to enable smooth updates for all the sections
        #
        # naming a non-existent section will effectively disable new smooth
        # updates but still allow removals to occur
        self._contents.append('SMOOTH_UPDATES = libs oldlibs')
        self._contents.append('IGNORE_CRUFT   = 1')

        # we don't support autopkgtest yet
        self._contents.append('ADT_ENABLE      = no')

    def set_archive_paths(self, from_path: str, to_path: str):
        assert not self._paths_set

        # paths for control files
        self._contents.append('UNSTABLE = {}'.format(from_path))
        self._contents.append('TESTING  = {}'.format(to_path))

        self._paths_set = True

    def set_components(self, components: List[str]):
        assert not self._components_set

        # DISABLED: removed from Britney
        # self._contents.append('COMPONENTS = {}'.format(', '.join(components)));
        self._components_set = True

    def set_partial_source(self, enabled: bool):
        """Set if the source suite is a partial suite.
        By default, package removal propagates to the target suite. To disable this,
        e.g. for partial suites like experimental or spu, set this to True.
        """
        self._partial_source = enabled

    def set_architectures(self, archs: List[str]):
        assert not self._archs_set

        # ensure arch:all isn't present in this list
        archs = list(filter(('all').__ne__, archs))
        arch_str = ' '.join(archs)

        # List of release architectures
        self._contents.append('ARCHITECTURES = {}'.format(arch_str))

        # if you're not in this list, arch: all packages are allowed to break on you
        self._contents.append('NOBREAKALL_ARCHES = {}'.format(arch_str))

        self._archs_set = True

    def set_broken_architectures(self, archs: List[str]):
        assert not self._broken_archs_set

        arch_str = ' '.join(archs)

        # if you're in this list, your packages may not stay in sync with the source
        self._contents.append('OUTOFSYNC_ARCHES  = {}'.format(arch_str))

        # if you're in this list, your uninstallability count may increase
        self._contents.append('BREAK_ARCHES      = {}'.format(arch_str))

        self._broken_archs_set = True

    def set_new_architectures(self, archs: List[str]):
        assert not self._new_archs_set

        arch_str = ' '.join(archs)

        # if you're in this list, you are a new architecture
        self._contents.append('NEW_ARCHES        = {}'.format(arch_str))

        self._new_archs_set = True

    def set_delays(self, delays: Dict[str, int]):
        assert not self._delays_set

        # ensure all priorities have a value
        delays_e: Dict[ChangesUrgency, int] = {}
        for prio_str, days in delays.items():
            prio = ChangesUrgency.from_string(prio_str)
            delays_e[prio] = int(days)
        for prio in ChangesUrgency:
            if prio not in delays_e:
                delays_e[prio] = 0

        # write delay config
        for prio, days in delays_e.items():
            self._contents.append('MINDAYS_{} = {}'.format(prio.to_string().upper(), str(int(days))))

        self._contents.append('DEFAULT_URGENCY   = medium')

        self._delays_set = True

    def set_hints(self, hints: List[SpearsHint]):

        self._hint_contents = []
        self._hint_contents.append('##')
        self._hint_contents.append('# Britney hints file for Laniakea')
        self._hint_contents.append('# This file is managed automatically *DO NOT* edit it manually.')
        self._hint_contents.append('##')
        self._hint_contents.append('')

        for hint in hints:
            self._hint_contents.append('# ' + hint.reason.replace('\n', '\n# '))
            self._hint_contents.append(hint.hint)
            self._hint_contents.append('')

    def save(self):
        # ensure essential directories exist
        hints_dir = os.path.join(self._base_dir, 'input', 'hints')
        os.makedirs(os.path.join(self._base_dir, 'output', 'target'), exist_ok=True)
        os.makedirs(os.path.join(self._base_dir, 'state'), exist_ok=True)
        os.makedirs(hints_dir, exist_ok=True)

        # ensure essential settings are set
        # NOTE: All of this seriously needs some refactoring, the direct translation from
        # D code is pretty bad at the moment.
        assert self._paths_set
        assert self._components_set
        assert self._archs_set
        if not self._broken_archs_set:
            self.set_broken_architectures([])
        if not self._new_archs_set:
            self.set_new_architectures([])
        if not self._delays_set:
            self.set_delays([])

        # save configuration
        conf_fname = os.path.join(self._base_dir, 'britney.conf')
        log.debug('Saving Britney config to "{}"'.format(conf_fname))

        conf_contents = self._contents.copy()
        if self._partial_source:
            conf_contents.append('PARTIAL_SOURCE    = true')

        with open(conf_fname, 'wt') as f:
            for line in conf_contents:
                f.write(line + '\n')

        if self._hint_contents:
            hints_fname = os.path.join(self._base_dir, 'input', 'hints', 'laniakea')
            with open(hints_fname, 'wt') as f:
                for line in self._hint_contents:
                    f.write(line + '\n')
