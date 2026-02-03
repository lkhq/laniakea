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
@click.option('--config', 'config_fname', default=None, type=str, help='Override the basic configuration used.')
@click.pass_context
def cli(ctx, verbose, version, config_fname):
    '''Administer a Laniakea instance.

    This utility allows you to perform a lot of administrative actions for
    Laniakea directly from the command-line.'''
    from laniakea import LocalConfig
    from laniakea.logging import set_verbose, configure_pkg_archive_logger
    from laniakea.utils.misc import ensure_laniakea_master_user

    set_verbose(verbose)
    if version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)

    if config_fname:
        LocalConfig(config_fname)

    # some safeguarding against running as root or any other "wrong" user
    ensure_laniakea_master_user(warn_only=True)

    # configure the archive action file logging
    configure_pkg_archive_logger()

    if ctx.invoked_subcommand is None:
        click.echo('No subcommand was provided. Can not continue.')
        sys.exit(1)


def _register_commands():
    '''Register lk-admin subcommands.'''

    import admincli.core as core

    cli.add_command(core.core)

    import admincli.archive as archive

    cli.add_command(archive.archive)

    import admincli.job as job

    cli.add_command(job.job)

    import admincli.synchrotron as synchrotron

    cli.add_command(synchrotron.synchrotron)

    import admincli.spears as spears

    cli.add_command(spears.spears)

    import admincli.ariadne as ariadne

    cli.add_command(ariadne.ariadne)

    import admincli.isotope as isotope

    cli.add_command(isotope.isotope)

    import admincli.planter as planter

    cli.add_command(planter.planter)

    import admincli.flatpak as flatpak

    cli.add_command(flatpak.flatpak)


def run(mainfile, args):
    from rich.traceback import install

    from laniakea.utils import set_process_title

    set_process_title('lk-admin')
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    global __mainfile
    __mainfile = mainfile

    install(show_locals=True, suppress=[click])
    _register_commands()
    cli()  # pylint: disable=no-value-for-parameter
