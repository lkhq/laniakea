# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click
import tomlkit

from .utils import input_str, print_note, print_header


@click.group()
def ariadne():
    '''Adjust package autobuilder settings.'''


def ariadne_set_value(key, value):
    from laniakea.db.core import LkModule, config_set_value

    config_set_value(LkModule.ARIADNE, key, value)


def _set_ariadne_config(*, indep_arch_affinity: str):
    if indep_arch_affinity == 'all':
        raise Exception('Architecture affinity for arch:all can not be arch:all as well.')
    if not indep_arch_affinity:
        raise Exception('Architecture affinity can not be empty.')

    ariadne_set_value('indep_arch_affinity', indep_arch_affinity)


@ariadne.command()
def configure_all():
    '''Configure this module.'''

    print_header('Configuring settings for Ariadne (package building)')

    arch_affinity = None
    while not arch_affinity:
        arch_affinity = input_str('Architecture affinity for arch:all / arch-indep packages')
        arch_affinity = arch_affinity.strip() if arch_affinity else None
        if arch_affinity == 'all':
            print_note('Architecture affinity for arch:all can not be arch:all as well.')
            arch_affinity = None

    _set_ariadne_config(indep_arch_affinity=arch_affinity)


@ariadne.command()
@click.argument('config_fname', nargs=1)
def update_from_config(config_fname):
    '''Add/update all settings from a TOML config file.'''
    with open(config_fname, 'r', encoding='utf-8') as f:
        conf = tomlkit.load(f)

    _set_ariadne_config(indep_arch_affinity=conf.get('indep_arch_affinity', ''))
