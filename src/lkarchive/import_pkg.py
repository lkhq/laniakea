# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import fnmatch

import click

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    NewPolicy,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.logging import log
from laniakea.archive.pkgimport import PackageImporter, ArchivePackageExistsError


def import_packages(
    session, rss: ArchiveRepoSuiteSettings, component_name: T.Optional[str], fnames: T.List[T.PathUnion]
):
    """Directly add packages to a repository, without any extra checks.
    Usually, a regulr upload will have a NEW review and a bunch of QA checks before being permitted into
    a repository, but occasionally a direct package import is useful too, which is what this command permits.
    """

    src_fnames = []
    bin_fnames = []
    for fname in fnames:
        if fname.endswith('.dsc'):
            src_fnames.append(fname)
        elif fname.endswith(('.deb', '.udeb')):
            bin_fnames.append(fname)
        elif fnmatch.fnmatch(fname, '*.tar.*') or fname.endswith(('.gz', '.buildinfo', '.changes')):
            # ignore source package components
            pass
        else:
            raise ValueError('File "{}" is no valid source or binary package!'.format(fname))

    if not src_fnames and not bin_fnames:
        raise ValueError('No valid source or binary packages found to import!')

    pi = PackageImporter(session, rss)
    pi.keep_source_packages = True

    # import sources
    for src_fname in src_fnames:
        try:
            pi.import_source(src_fname, component_name, new_policy=NewPolicy.NEVER_NEW)
        except ArchivePackageExistsError:
            log.info('Skipping %s: Already exists in the archive', os.path.basename(src_fname))
    session.commit()

    # import binaries
    for bin_fname in bin_fnames:
        try:
            pi.import_binary(bin_fname, component_name)
        except ArchivePackageExistsError:
            log.info('Skipping %s: Already exists in the archive', os.path.basename(bin_fname))


@click.command('import')
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
    help='Name of the suite to act on, if not set all suites will be processed',
)
@click.option(
    '--component',
    '-c',
    'component_name',
    help='Name of the component to import into, will be read from the package file if not set.',
)
@click.argument('fnames', nargs=-1, type=click.Path())
def import_pkg(
    repo_name: T.Optional[str], suite_name: str, component_name: T.Optional[str], fnames: T.List[T.PathUnion]
):
    """Directly import packages into a repository, without any extra checks."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    if not fnames:
        click.echo('Nothing to import.', err=True)
        sys.exit(1)

    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
        if not repo:
            click.echo('Unable to find repository with name {}!'.format(repo_name), err=True)
            sys.exit(1)

        rss = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(ArchiveRepoSuiteSettings.repo_id == repo.id, ArchiveRepoSuiteSettings.suite.has(name=suite_name))
            .one_or_none()
        )
        if not rss:
            click.echo('Unable to find suite "{}" in repository "{}"'.format(suite_name, repo_name), err=True)
            sys.exit(1)

        try:
            import_packages(session, rss, component_name, fnames)
        except Exception as e:
            click.echo('Package import failed: {}'.format(str(e)), err=True)
            sys.exit(5)
