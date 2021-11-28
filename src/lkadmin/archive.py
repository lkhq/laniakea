# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import toml
import click

from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    ArchiveUploader,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    session_scope,
)

from .utils import ClickAliasedGroup, input_str, input_list, print_error_exit


@click.group(cls=ClickAliasedGroup)
def archive():
    '''Configure package archive settings.'''


def _add_repo(name: str, origin: str, is_debug: bool = False, debug_for: str = None):
    '''Create a new repository (helper function).'''

    if is_debug and not debug_for:
        raise ValueError(
            'Repo "{}" is marked as debug repo, but no repo name that it contains '
            'debug symbols for was given.'.format(name)
        )

    name = name.lower()
    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == name).one_or_none()
        if not repo:
            repo = ArchiveRepository(name)
            session.add(repo)
        repo.origin_name = origin
        repo.is_debug = is_debug
        if is_debug:
            nd_repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == debug_for).one_or_none()
            if not nd_repo:
                raise ValueError('Repository with name "{}" was not found.'.format(debug_for))
            nd_repo.debug_repo = repo


@archive.command(aliases=['r-a'])
@click.option('--name', prompt=True, type=str, help='Name of the repository, e.g. "master"')
@click.option('--origin', prompt=True, type=str, default='', help='Repository origin, e.g. "Debian Project"')
@click.option(
    '--is-debug',
    prompt=True,
    default=False,
    is_flag=True,
    help='Whether this repository contains only debug symbol packages.',
)
@click.option(
    '--debug-for-repo', type=str, default=None, help='Repository name this repository contains debug symbols for.'
)
def repo_add(name: str, origin: str, is_debug: bool = False, debug_for_repo: str = None):
    '''Create a new repository.'''

    if is_debug and not debug_for_repo:
        debug_for_repo = input_str('Name of the repository this debug repo contains symbols for')

    _add_repo(name, origin, is_debug, debug_for_repo)


@archive.command(aliases=['c-a'])
@click.option('--name', prompt=True, type=str, help='Name of the component, e.g. "main"')
@click.option(
    '--summary', prompt=True, type=str, default='', help='Short description of the component, e.g. "Supported packages"'
)
def component_add(name: str, summary: str):
    '''Add a new archive component.'''

    name = name.lower()
    with session_scope() as session:
        component = session.query(ArchiveComponent).filter(ArchiveComponent.name == name).one_or_none()
        if not component:
            component = ArchiveComponent(name)
            session.add(component)
        component.summary = summary


@archive.command(aliases=['a-a'])
@click.option('--name', prompt=True, type=str, help='Name of the architecture, e.g. "amd64"')
@click.option(
    '--summary',
    prompt=True,
    type=str,
    default='',
    help='Short description of the architecture, e.g. "AMD x86-64 architecture"',
)
def architecture_add(name: str, summary: str):
    '''Register a new archive architecture.'''

    name = name.lower()
    with session_scope() as session:
        arch = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == name).one_or_none()
        if not arch:
            arch = ArchiveArchitecture(name)
            session.add(arch)
        arch.summary = summary


def _add_uploader(
    repo_name,
    email,
    fingerprints,
    is_human,
    allow_source_uploads=True,
    allow_binary_uploads=True,
    always_review=False,
    allow_packages=None,
):
    '''Set up a new entity who is allowed to upload packages.'''

    if not allow_packages:
        allow_packages = []
    if not fingerprints:
        raise ValueError('Can not add uploader without GPG fingerprints.')

    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
        if not repo:
            print_error_exit('Repository with name "{}" does not exist.'.format(repo_name))

        uploader = session.query(ArchiveUploader).filter(ArchiveUploader.email == email).one_or_none()
        if not uploader:
            uploader = ArchiveUploader(email)
            session.add(uploader)
        uploader.pgp_fingerprints = fingerprints
        uploader.is_human = is_human
        uploader.allow_source_uploads = allow_source_uploads
        uploader.allow_binary_uploads = allow_binary_uploads
        uploader.always_review = always_review
        uploader.allowed_packages = allow_packages
        if repo not in uploader.repos:
            uploader.repos.append(repo)


@archive.command(aliases=['u-a'])
@click.option(
    '--repo',
    'repo_name',
    prompt=True,
    type=str,
    default=lambda: LocalConfig().master_repo_name,
    help='Name of the repository this entity is allowed to upload to',
)
@click.option('--email', prompt=True, type=str, help='E-Mail address of the new uploader')
@click.option(
    '--fingerprint', 'fingerprints', multiple=True, type=str, default=None, help='PGP fingerprint for this new uploader'
)
@click.option(
    '--human/--no-human',
    'is_human',
    prompt=True,
    default=True,
    help='Whether the new uploader is human or an automaton.',
)
@click.option(
    '--allow-source-uploads', prompt=True, default=True, is_flag=True, help='Allow uploads of source packages.'
)
@click.option(
    '--allow-binary-uploads', prompt=True, default=True, is_flag=True, help='Allow uploads of binary packages.'
)
@click.option(
    '--always-review',
    prompt=True,
    default=False,
    is_flag=True,
    help='Uploads of this uploader will never be published immediately and always marked for review first.',
)
@click.option(
    '--allow-package',
    'allow_packages',
    multiple=True,
    default=[],
    help='Allow only specific packages to be uploaded by this uploader.',
)
def uploader_add(
    repo_name,
    email,
    fingerprints,
    is_human,
    allow_source_uploads=True,
    allow_binary_uploads=True,
    always_review=False,
    allow_packages=None,
):
    '''Set up a new entity who is allowed to upload packages.'''

    if not fingerprints:
        fingerprints = input_list('Fingerprints')
    if not allow_packages:
        allow_packages = input_list('Allowed Packages', allow_empty=True)

    _add_uploader(
        repo_name,
        email,
        fingerprints,
        is_human,
        allow_source_uploads,
        allow_binary_uploads,
        always_review,
        allow_packages,
    )


def _add_suite(
    name,
    alias,
    summary,
    version,
    arch_names=None,
    component_names=None,
    parent_names=None,
    is_debug=False,
    debug_suite_for=None,
):
    '''Register a new suite with the archive.'''

    name = name.lower()
    alias = alias.lower()

    if not alias:
        alias = None
    if not version:
        version = None
    if not summary:
        summary = None

    if not arch_names:
        raise ValueError('Can not add a suite without any architectures.')
    if not component_names:
        raise ValueError('Can not add a suite without any component.')
    if not parent_names:
        parent_names = []

    if is_debug and not debug_suite_for:
        raise ValueError(
            'Suite "{}" is marked as debug suite, but no name of the suite '
            'that it contains debug symbols for was given. '.format(name)
        )

    with session_scope() as session:
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == name).one_or_none()
        if not suite:
            suite = ArchiveSuite(name, alias)
            session.add(suite)
        suite.alias = alias
        suite.summary = summary
        suite.version = version

        if is_debug:
            suite.is_debug = is_debug
            parent_nodebug_suite = (
                session.query(ArchiveSuite).filter(ArchiveSuite.name == debug_suite_for).one_or_none()
            )
            if not parent_nodebug_suite:
                print_error_exit('Non-debug parent suite with name "{}" does not exist.'.format(debug_suite_for))
            suite.debug_suite_for = parent_nodebug_suite

        for cname in component_names:
            component = session.query(ArchiveComponent).filter(ArchiveComponent.name == cname).one_or_none()
            if not component:
                print_error_exit('Component with name "{}" does not exist.'.format(cname))
            if component not in suite.components:
                suite.components.append(component)

        # always add the "all" architecture
        suite.architectures.append(session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == 'all').one())

        # add the other architectures
        for aname in arch_names:
            arch = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == aname).one_or_none()
            if not arch:
                print_error_exit('Architecture with name "{}" does not exist.'.format(aname))
            if arch not in suite.architectures:
                suite.architectures.append(arch)

        # add suite parents
        for pname in parent_names:
            parent = session.query(ArchiveSuite).filter(ArchiveSuite.name == pname).one_or_none()
            if not parent:
                print_error_exit('Parent suite with name "{}" does not exist.'.format(pname))
            if parent not in suite.parents:
                suite.parents.append(parent)


@archive.command(aliases=['s-a'])
@click.option('--name', prompt=True, type=str, help='Name of the suite (e.g. "sid")')
@click.option('--alias', prompt=True, type=str, default='', help='Alias name of the suite (e.g. "unstable")')
@click.option('--summary', prompt=True, type=str, default='', help='Short suite description')
@click.option('--version', prompt=True, type=str, default='', help='Distribution version this suite belongs to')
@click.option('--arch', 'arch_names', multiple=True, type=str, help='Architectures this suite can contain')
@click.option('--component', 'component_names', multiple=True, type=str, help='Components this suite contains')
@click.option('--parent', 'parent_names', multiple=True, type=str, help='Parent suite names')
@click.option(
    '--is-debug',
    prompt=True,
    default=False,
    is_flag=True,
    help='Whether this suite contains only debug symbol packages.',
)
@click.option(
    '--debug-suite-for', type=str, default=None, help='Suite name this repository contains debug symbols for.'
)
def suite_add(
    name,
    alias,
    summary,
    version,
    arch_names=None,
    component_names=None,
    parent_names=None,
    is_debug: bool = False,
    debug_suite_for: str = None,
):
    '''Register a new suite with the archive.'''

    if not arch_names:
        arch_names = input_list('Architectures')
    if not component_names:
        component_names = input_list('Archive Components')
    if not parent_names:
        parent_names = input_list('Suite Parents', allow_empty=True)
    if is_debug and not debug_suite_for:
        debug_suite_for = input_str('Name of the suite this debug suite contains symbols for')

    _add_suite(name, alias, summary, version, arch_names, component_names, parent_names, is_debug, debug_suite_for)


def _add_suite_to_repo(
    repo_name: str,
    suite_name: str,
    accept_uploads=True,
    devel_target=False,
    auto_overrides=False,
    manual_accept=False,
    signingkeys=None,
    announce_emails=None,
):
    '''Add suite to a repository.'''

    if not signingkeys:
        raise ValueError('Can not associate a suite with a repository without signingkeys set.')
    if announce_emails is None:
        announce_emails = []

    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
        if not repo:
            print_error_exit('Repository with name "{}" does not exist.'.format(repo_name))
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one_or_none()
        if not suite:
            print_error_exit('Suite with name "{}" does not exist.'.format(suite_name))

        rs_settings = (
            session.query(ArchiveRepoSuiteSettings).filter_by(repo_id=repo.id, suite_id=suite.id).one_or_none()
        )
        if not rs_settings:
            rs_settings = ArchiveRepoSuiteSettings(repo, suite)
            session.add(rs_settings)

        rs_settings.accept_uploads = accept_uploads
        rs_settings.devel_target = devel_target
        rs_settings.auto_overrides = auto_overrides
        rs_settings.manual_accept = manual_accept
        rs_settings.signingkeys = signingkeys
        rs_settings.announce_emails = announce_emails


@archive.command(aliases=['r-a-s'])
@click.option(
    '--repo',
    'repo_name',
    prompt=True,
    type=str,
    default=lambda: LocalConfig().master_repo_name,
    help='Name of the repository, e.g. "master"',
)
@click.option('--suite', 'suite_name', prompt=True, type=str, help='Name of the suite, e.g. "sid"')
@click.option(
    '--accept-uploads',
    prompt='Accepts Uploads',
    default=True,
    is_flag=True,
    help='Whether the suite accepts uploads in this repository.',
)
@click.option(
    '--devel-target',
    prompt='Development Target',
    default=False,
    is_flag=True,
    help='Whether the suite accepts uploads in this repository.',
)
@click.option(
    '--auto-overrides',
    prompt='Automatic Overrides',
    default=False,
    is_flag=True,
    help='Automatically process overrides for the suite, if possible.',
)
@click.option(
    '--manual-accept',
    prompt='Manual Accept For Everything',
    default=False,
    is_flag=True,
    help='Whether every package uplod needs to be accepted manually.',
)
@click.option(
    '--signingkey',
    'signingkeys',
    multiple=True,
    type=str,
    default=None,
    help='PGP fingerprint of keys used to sign this suite in the selected repository',
)
@click.option(
    '--announce',
    'announce_emails',
    multiple=True,
    type=str,
    default=None,
    help='E-Mail addresses to announce changes to.',
)
def repo_add_suite(
    repo_name: str,
    suite_name: str,
    accept_uploads=True,
    devel_target=False,
    auto_overrides=False,
    manual_accept=False,
    signingkeys=None,
    announce_emails=None,
):
    '''Add suite to a repository.'''

    if not signingkeys:
        signingkeys = input_list('PGP Signing Key Fingerprints')
    if announce_emails is None:
        announce_emails = input_list('Announce E-Mails', allow_empty=True)

    _add_suite_to_repo(
        repo_name, suite_name, accept_uploads, devel_target, auto_overrides, manual_accept, signingkeys, announce_emails
    )


@archive.command()
@click.argument('config_fname', nargs=1)
def add_from_config(config_fname):
    '''Add/update all archive settings from a TOML config file.'''
    with open(config_fname, 'r', encoding='utf-8') as f:
        conf = toml.load(f)

    for repo_d in conf.get('Repositories', []):
        _add_repo(**repo_d)
    for component_d in conf.get('Components', []):
        component_add.callback(**component_d)
    for arch_d in conf.get('Architectures', []):
        architecture_add.callback(**arch_d)
    for suite_d in conf.get('Suites', []):
        _add_suite(**suite_d)
    for rss_d in conf.get('RepoSuiteSettings', []):
        _add_suite_to_repo(**rss_d)
    for uploader_d in conf.get('Uploaders', []):
        _add_uploader(**uploader_d)
