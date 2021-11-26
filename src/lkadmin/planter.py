# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys

import click

from .utils import input_str, print_header


@click.group()
def planter():
    '''Configure settings for Planter (seed packages)'''
    pass


@planter.command()
def configure_all():
    '''Configure this module.'''

    def planter_set_value(key, value):
        from laniakea.db.core import LkModule, config_set_value

        config_set_value(LkModule.PLANTER, key, value)

    print_header('Configuring settings for Planter (metapackages / germinator)')

    git_url = input_str('Git clone URL for the germinate metapackage sources')
    if git_url:
        planter_set_value('git_seeds_url', git_url)
