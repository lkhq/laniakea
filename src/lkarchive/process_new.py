# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import sys

import click

import laniakea.typing as T
from laniakea.db import ArchiveRepository, session_scope


@click.command()
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
@click.option(
    '--suite',
    '-s',
    'suite_name',
    default=None,
    help='Name of the suite to act on, if not set all suites will be processed',
)
def process_new(repo_name: T.Optional[str] = None, suite_name: T.Optional[str] = None):
    """Interactively process source packages in the new packages queue."""

    with session_scope() as session:
        if repo_name:
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
            if not repo:
                click.echo('Unable to find repository with name {}!'.format(repo_name), err=True)
                sys.exit(1)
            repos = [repo]
        else:
            repos = session.query(ArchiveRepository).all()
