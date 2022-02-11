# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import click

from laniakea import LocalConfig
from laniakea.db import FlatpakRepository, session_scope, config_get_distro_tag
from laniakea.flatpak_util import FlatpakUtil

from .utils import input_str, input_list, print_note, print_header, print_error_exit


@click.group()
def flatpak():
    '''Configure settings for Flatpak repositories.'''


@flatpak.command()
def add_repo():
    '''Create new Flatpak repository.'''

    print_header('Add new Flatpak repository')
    lconf = LocalConfig()
    fputil = FlatpakUtil()

    with session_scope() as session:
        repo_name = input_str('Machine-readable name of this repository (e.g. "{}")'.format(config_get_distro_tag()))
        repo_name = repo_name.replace(' ', '_')

        repo = FlatpakRepository(repo_name)
        repo_path = os.path.join(lconf.archive_flatpak_root_dir, repo.name)
        if os.path.isdir(repo_path):
            print_error_exit('Repository path at "{}" already exists, can not continue!'.format(repo_path))
            return
        repo.default_branch = 'stable'

        collection_id = None
        while True:
            collection_id = input_str(
                'Set collection-id (a globally unique reverse DNS value to identify the collection of Flatpaks in this repository)'
            )
            if len(collection_id.split('.')) < 3:
                print_note('Please enter a rDNS ID!')
            else:
                break
        repo.collection_id = collection_id

        repo.title = input_str('Human-readable repository title')
        repo.comment = input_str('Short description / tagline of this repository')
        repo.description = input_str('Longer repository description', allow_empty=True)

        repo.url_homepage = input_str('Homepage URL of this repository', allow_empty=True)
        repo.url_icon = input_str('URL of a repository icon', allow_empty=True)

        repo.gpg_key_id = input_str('GPG key ID of the key used to sign this repository')

        repo.allowed_branches = input_list('List of permitted branch names in this repository', allow_empty=True)
        if 'stable' not in repo.allowed_branches:
            repo.allowed_branches.append('stable')

        fputil.init_repo(repo, repo_path)
        session.add(repo)
