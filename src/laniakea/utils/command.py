# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2018 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2012-2013 Paul Tagliamonte <paultag@debian.org>
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

import sys
import shlex
import subprocess


class SubprocessError(Exception):
    def __init__(self, out, err, ret, cmd):
        self.out = out
        self.err = err
        self.ret = ret
        self.cmd = cmd

    def __str__(self):
        return "%s: %d\n%s" % (str(self.cmd), self.ret, str(self.err))


# Input may be a byte string, a unicode string, or a file-like object
def run_command(command, input=None, capture_output=True):
    if not isinstance(command, list):
        command = shlex.split(command)

    if not input:
        input = None
    elif isinstance(input, str):
        input = input.encode('utf-8')
    elif not isinstance(input, bytes):
        input = input.read()

    p_stdout = None
    p_stderr = None
    if capture_output:
        p_stdout = subprocess.PIPE
        p_stderr = subprocess.PIPE

    try:
        pipe = subprocess.Popen(command,
                                shell=False,
                                stdin=subprocess.PIPE,
                                stdout=p_stdout,
                                stderr=p_stderr,
                                )
    except OSError as e:
        return (None, str(e), -1)

    (output, stderr) = pipe.communicate(input=input)
    if capture_output:
        (output, stderr) = (c.decode('utf-8', errors='ignore') for c in (output, stderr))
    return (output, stderr, pipe.returncode)


def safe_run(cmd, input=None, expected=0):
    if not isinstance(expected, tuple):
        expected = (expected, )

    out, err, ret = run_command(cmd, input=input)

    if ret not in expected:
        raise SubprocessError(out, err, ret, cmd)

    return out, err, ret


def run_forwarded(command, cwd=None, print_output=False):
    '''
    Run a command, optionally forwarding all output to the current stdout and return
    the output as well.
    '''
    if not isinstance(command, list):
        command = shlex.split(command)

    output = ''
    proc = subprocess.Popen(command,
                            cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    while True:
        line = proc.stdout.readline()
        if proc.poll() is not None:
            break
        line_str = str(line, 'utf-8', 'replace')
        sys.stdout.write(line_str)
        output = output + line_str

    return (output, proc.returncode)


def safe_run_forwarded(command, expected=0, cwd=None, print_output=False):
    if not isinstance(expected, tuple):
        expected = (expected, )

    out, ret = run_forwarded(command, cwd=cwd, print_output=print_output)

    if ret not in expected:
        raise SubprocessError(out, '', ret, command)

    return out, ret
