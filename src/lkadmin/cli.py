# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys

import click

__mainfile = None


@click.group(invoke_without_command=True)
@click.option('--verbose', envvar='VERBOSE', default=False, is_flag=True,
              help='Enable debug messages.')
@click.option('--version', default=False, is_flag=True,
              help='Display the version of Laniakea itself.')
@click.pass_context
def cli(ctx, verbose, version):
    '''Administer a Laniakea instance.

     This utility allows you to perform a lot of administrative actions for
     Laniakea directly from the command-line.'''
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
    ''' Register lk-admin subcommands. '''

    import lkadmin.core as core
    cli.add_command(core.core)

    import lkadmin.archive as archive
    cli.add_command(archive.archive)

    import lkadmin.job as job
    cli.add_command(job.job)

    import lkadmin.synchrotron as synchrotron
    cli.add_command(synchrotron.synchrotron)

    import lkadmin.spears as spears
    cli.add_command(spears.spears)

    import lkadmin.ariadne as ariadne
    cli.add_command(ariadne.ariadne)

    import lkadmin.isotope as isotope
    cli.add_command(isotope.isotope)

    import lkadmin.planter as planter
    cli.add_command(planter.planter)

    import lkadmin.flatpak as flatpak
    cli.add_command(flatpak.flatpak)


def run(mainfile, args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    global __mainfile
    __mainfile = mainfile

    _register_commands()
    cli()
