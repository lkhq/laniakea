# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import click

from .utils import input_str, print_note, print_header


@click.group()
def ariadne():
    '''Adjust package autobuilder settings.'''


@ariadne.command()
def configure_all():
    '''Configure this module.'''

    def ariadne_set_value(key, value):
        from laniakea.db.core import LkModule, config_set_value

        config_set_value(LkModule.ARIADNE, key, value)

    print_header('Configuring settings for Ariadne (package building)')

    arch_affinity = None
    while not arch_affinity:
        arch_affinity = input_str('Architecture affinity for arch:all / arch-indep packages')
        arch_affinity = arch_affinity.strip() if arch_affinity else None
        if arch_affinity == 'all':
            print_note('Architecture affinity for arch:all can not be arch:all as well.')
            arch_affinity = None

    ariadne_set_value('indep_arch_affinity', arch_affinity)
