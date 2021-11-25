# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2019-2021 Robbin Bonthond <robbin@bonthond.com>
#
# SPDX-License-Identifier: LGPL-3.0+

import readline  # noqa: F401 pylint: disable=unused-import

import click


class ClickAliasedGroup(click.Group):
    def __init__(self, *args, **kwargs):
        super(ClickAliasedGroup, self).__init__(*args, **kwargs)
        self._commands = {}
        self._aliases = {}

    def command(self, *args, **kwargs):
        aliases = kwargs.pop('aliases', [])
        decorator = super(ClickAliasedGroup, self).command(*args, **kwargs)
        if not aliases:
            return decorator

        def _decorator(f):
            cmd = decorator(f)
            if aliases:
                self._commands[cmd.name] = aliases
                for alias in aliases:
                    self._aliases[alias] = cmd.name
            return cmd

        return _decorator

    def group(self, *args, **kwargs):
        aliases = kwargs.pop('aliases', [])
        decorator = super(ClickAliasedGroup, self).group(*args, **kwargs)
        if not aliases:
            return decorator

        def _decorator(f):
            cmd = decorator(f)
            if aliases:
                self._commands[cmd.name] = aliases
                for alias in aliases:
                    self._aliases[alias] = cmd.name
            return cmd

        return _decorator

    def resolve_alias(self, cmd_name):
        if cmd_name in self._aliases:
            return self._aliases[cmd_name]
        return cmd_name

    def get_command(self, ctx, cmd_name):
        cmd_name = self.resolve_alias(cmd_name)
        command = super(ClickAliasedGroup, self).get_command(ctx, cmd_name)
        if command:
            return command

    def format_commands(self, ctx, formatter):
        rows = []

        sub_commands = self.list_commands(ctx)

        max_len = max(len(cmd) for cmd in sub_commands)
        limit = formatter.width - 6 - max_len

        for sub_command in sub_commands:
            cmd = self.get_command(ctx, sub_command)
            if cmd is None:
                continue
            if hasattr(cmd, 'hidden') and cmd.hidden:
                continue
            if sub_command in self._commands:
                aliases = ','.join(sorted(self._commands[sub_command]))
                sub_command = '{0} ({1})'.format(sub_command, aliases)
            cmd_help = cmd.get_short_help_str(limit)
            rows.append((sub_command, cmd_help))

        if rows:
            with formatter.section('Commands'):
                formatter.write_dl(rows)

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
