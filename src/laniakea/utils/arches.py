# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from laniakea.utils.command import run_command


def arch_matches(arch, alias):
    '''
    Check if given arch `arch` matches the other arch `alias`. This is most
    useful for the complex any-* rules.
    '''

    if arch == alias:
        return True

    if arch == 'all' or arch == 'source':
        # These pseudo-arches does not match any wildcards or aliases
        return False

    if alias == 'any':
        # The 'any' wildcard matches all *real* architectures
        return True

    if alias == 'linux-any':
        # GNU/Linux arches are named <cpuabi>
        # Other Linux arches are named <libc>-linux-<cpuabi>
        return '-' not in arch or 'linux' in arch.split('-')

    if alias.endswith('-any'):
        # Non-Linux GNU/<os> arches are named <os>-<cpuabi>
        # Other non-Linux arches are named <libc>-<os>-<cpuabi>
        osname, _ = alias.split('-', 1)
        return osname in arch.split('-')

    if '-' not in arch and '-' not in alias:
        return False

    # This is a performance disaster
    # Hopefully we'll rarely get here
    out, err, ret = run_command([
        "/usr/bin/dpkg-architecture",
        "-a%s" % (arch),
        "-i%s" % (alias)
    ])
    return ret == 0


def any_arch_matches(architectures, aliases):
    '''
    Check if any architecture in iterable `architectures` matches any architecture wildcard
    in `aliases`.
    '''

    if type(architectures) is str:
        architectures = [architectures]
    if type(aliases) is str:
        aliases = [aliases]

    for arch in architectures:
        for alias in aliases:
            if arch_matches(arch, alias):
                return True
    return False
