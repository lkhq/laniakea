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
    from laniakea.logging import set_verbose, configure_pkg_archive_logger

    set_verbose(verbose)
    if version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)

    # configure the archive action file logging
    configure_pkg_archive_logger()

    if ctx.invoked_subcommand is None:
        click.echo('No subcommand was provided. Can not continue.')
        sys.exit(1)


def _register_commands():
    '''Register lk-archive subcommands.'''

    from .publish import publish

    cli.add_command(publish)

    import lkarchive.data_import as dip

    cli.add_command(dip.import_pkg)
    cli.add_command(dip.import_heidi_result)
    cli.add_command(dip.import_repository)
    cli.add_command(dip.export_package_list)

    import lkarchive.manage_pkg as mgr

    cli.add_command(mgr.cmd_list)
    cli.add_command(mgr.remove)
    cli.add_command(mgr.expire)
    cli.add_command(mgr.cmd_copy_package)
    cli.add_command(mgr.show_overrides)
    cli.add_command(mgr.change_override)

    from lkarchive.process_new import process_new

    cli.add_command(process_new)

    import lkarchive.validate as validate

    cli.add_command(validate.check_integrity)

    import lkarchive.ariadne as ariadne

    cli.add_command(ariadne.update_jobs)


def run(mainfile, args):
    from rich.traceback import install

    from laniakea.utils.misc import set_process_title, ensure_laniakea_master_user

    set_process_title('lk-archive')
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    global __mainfile
    __mainfile = mainfile

    ensure_laniakea_master_user(warn_only=True)

    install(show_locals=True, suppress=[click])
    _register_commands()
    cli()  # pylint: disable=no-value-for-parameter
