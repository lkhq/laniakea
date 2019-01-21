# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import readline


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
    print('\n== {} =='.format(msg))


def print_done(msg):
    print('-> {}'.format(msg))


def print_note(msg):
    print('! {}'.format(msg))

def print_error_exit(msg):
    from sys import exit
    print(msg)
    exit(1)
