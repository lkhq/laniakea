# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import readline  # noqa: F401 pylint: disable=unused-import


def input_str(prompt, allow_empty=False):
    while True:
        s = input('{}: '.format(prompt))
        if s:
            return s
        elif allow_empty:
            return None


def input_list(prompt, allow_empty=False):
    while True:
        s = input('{} [list]: '.format(prompt))
        if s:
            return s.split(' ')
        elif allow_empty:
            return []


def input_bool(prompt, allow_empty=False):
    while True:
        s = input('{} [y/n]: '.format(prompt))

        if s == 'y' or s == 'yes' or s == 'Y':
            return True
        elif s == 'n' or s == 'no' or s == 'N':
            return False
        else:
            if allow_empty:
                print('Unknown input, assuming "No".')
                return False
            else:
                print('Unknown input, please select "yes" or "no".')


def input_int(prompt, allow_empty=False):
    while True:
        s = input('{} [number]: '.format(prompt))
        try:
            i = int(s)
            return i
        except ValueError:
            print('Please enter a valid integer!')


def print_header(msg):
    print('\n{}'.format(msg))
    print('~' * len(msg))


def print_section(msg):
    print('\n## {}'.format(msg))


def print_done(msg):
    print('-> {}'.format(msg))


def print_note(msg):
    print('! {}'.format(msg))


def print_error_exit(msg):
    import sys
    print(msg, file=sys.stderr)
    sys.exit(1)
