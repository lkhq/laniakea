#!/usr/bin/env python3
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
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser
import logging as log
from laniakea import LocalConfig, LkModule
from laniakea.git import Git
from laniakea.logging import get_verbose
from laniakea.db import session_factory, ArchiveSuite, config_get_value


class Germinate:

    def __init__(self):
        from laniakea.db import config_get_project_name

        # default to system germinator (usually /usr/bin/germinate)
        self._germinate_exe = 'germinate'

        self._lconf = LocalConfig()
        self._project_name = config_get_project_name()

        self._metapackage_git_url = config_get_value(LkModule.PLANTER, 'git_seeds_url')

        workspace = os.path.join(self._lconf.workspace, 'planter')
        os.makedirs(workspace, exist_ok=True)

        # meta package / seed source directory
        self._meta_src_dir = os.path.join(workspace, 'meta')

        # output dir
        self._results_base_dir = os.path.join(workspace, 'results')

    def _run_germinate(self, wdir, args):
        from laniakea.utils import run_command

        ge_args = [self._germinate_exe]
        ge_args.extend(args)

        out, err, ret = run_command(ge_args, capture_output=not get_verbose())
        if ret != 0:
            return False, '{}\n{}'.format(out, err)
        return True, out

    def _update_seed_data(self):
        git = Git()
        git.location = self._meta_src_dir
        if os.path.isdir(os.path.join(self._meta_src_dir, '.git')):
            git.pull()
        else:
            os.makedirs(self._meta_src_dir, exist_ok=True)
            git.clone(self._metapackage_git_url)

    def run(self):
        session = session_factory()
        dev_suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.accept_uploads == True).one()  # noqa: E712

        # update the seed (contained in the metapackage repository)
        self._update_seed_data()

        # NOTE: We make a hardcoded assumption on where the seed is located.
        # Since germinate expects it there currently, this isn't an issue today,
        # but could become one in future.
        seed_src_dir = os.path.join(self._meta_src_dir, 'seed')

        # create target directory
        results_dir = os.path.join(self._results_base_dir, '{}.{}'.format(self._project_name.lower(), dev_suite.name))
        os.makedirs(results_dir, exist_ok=True)

        # prepare parameters
        ge_args = ['-S', 'file://' + seed_src_dir,  # seed source
                   '-s', dev_suite.name,  # suite name
                   '-d', dev_suite.name,  # suite / dist name
                   '-m', 'file://' + self._lconf.archive_root_dir,  # mirror
                   '-c', ' '.join([c.name for c in dev_suite.components]),  # components to check
                   '-a', dev_suite.primary_architecture.name]
        # NOTE: Maybe we want to limit the seed to only stuff in the primary (main) component?

        # execute germinator
        ret, out = self._run_germinate(results_dir, ge_args)

        if not ret:
            log.error('Germinate run has failed: {}'.format(out))
            return False

        return True


def command_run(options):
    ''' Update Germinator data '''

    germinate = Germinate()
    if not germinate.run():
        sys.exit(3)


def create_parser(formatter_class=None):
    ''' Create Planter CLI argument parser '''

    parser = ArgumentParser(description='Update seed information using Germinator.')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('run', help='Run Germinator and update data.')
    sp.set_defaults(func=command_run)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
