# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys

import click

__mainfile = None


@click.group(invoke_without_command=True)
@click.option('--verbose', envvar='VERBOSE', default=False, is_flag=True, help='Enable debug messages.')
@click.option('--version', default=False, is_flag=True, help='Display the version of Laniakea itself.')
@click.pass_context
def cli(ctx, verbose, version):
    '''Manage the package archive

    This utility allows you to query and manage archive repositories of Laniakea,
    but does not allow making wide administrative changes to the archive (like creating
    new repositories or suites).
    '''
    if verbose:
        from laniakea.logging import set_verbose

        set_verbose(True)
    if version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)
    if ctx.invoked_subcommand is None:
        click.echo('No subcommand was provided. Can not continue.')
        sys.exit(1)


def _register_commands():
    '''Register lk-archive subcommands.'''

    from publish import publish

    cli.add_command(publish)

    from import_pkg import import_pkg

    cli.add_command(import_pkg)

    import manage_pkg as mgr

    cli.add_command(mgr.list)
    cli.add_command(mgr.remove)
    cli.add_command(mgr.expire)

    from process_new import process_new

    cli.add_command(process_new)


def run(mainfile, args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    global __mainfile
    __mainfile = mainfile

    _register_commands()
    cli()  # pylint: disable=no-value-for-parameter
