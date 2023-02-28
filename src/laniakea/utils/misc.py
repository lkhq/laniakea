# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import sys
import time
import fcntl
import collections
from datetime import datetime
from contextlib import contextmanager

import requests

import laniakea.typing as T
from laniakea.logging import log


def get_dir_shorthand_for_uuid(uuid):
    '''
    Get short prefix for UUIDs for use in directory names.
    '''
    s = str(uuid)

    if len(s) > 2:
        return s[0:2]
    return None


def random_string(length=8):
    '''
    Generate a random alphanumerical string with length :length.
    '''
    import random
    import string

    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])


@contextmanager
def cd(where):
    ncwd = os.getcwd()
    try:
        yield os.chdir(where)
    finally:
        os.chdir(ncwd)


def listify(item):
    '''
    Return a list of :item, unless :item already is a list.
    '''
    if not item:
        return []
    if type(item) == list:
        return item
    if isinstance(item, collections.abc.Sequence):
        return list(item)
    return [item]


def stringify(item: T.Any):
    '''
    Convert anything into a string, if it isn't one already.
    Assume UTF-8 encoding if we have bytes.
    '''
    if type(item) is str:
        return item
    if type(item) is bytes:
        return str(item, 'utf-8')

    return str(item)


re_remote_url = re.compile('^(https?|ftps?)://')


def is_remote_url(uri):
    '''Check if string contains a remote URI.'''
    return re_remote_url.match(uri) is not None


def download_file(url, fname, check=False, headers: dict = None, **kwargs):
    if not headers:
        headers = {}

    hdr = {'user-agent': 'laniakea/0.0.1'}
    hdr.update(headers)

    r = requests.get(url, stream=True, headers=hdr, timeout=60, **kwargs)
    if r.status_code == 200:
        with open(fname, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)
        return r.status_code

    if check:
        raise Exception('Unable to download file "{}". Status: {}'.format(url, r.status_code))
    return r.status_code


def split_strip(s: str, sep: str):
    '''Split a string, removing empty segments from the result and stripping the individual parts'''
    res = []
    for part in s.split(sep):
        if part:
            res.append(part.strip())
    return res


def safe_strip(s: T.Optional[str]):
    """Strip a string and handle None"""
    return s if not s else s.strip()


def datetime_to_rfc2822_string(dt: datetime):
    """Convert a datetime object into an RFC2822 date string."""
    from email import utils

    return utils.format_datetime(dt)


class ProcessFileLock:
    """
    Simple wy to prevent multiple processes from executing the same code via a file lock.
    """

    def __init__(self, name: str):
        """
        :param name: Unique name of the lock.
        """
        self._name = name
        self._lock_file_fd = -1
        self._lock_dir = os.path.join('/usr/user', str(os.geteuid()))
        if not os.path.isdir(self._lock_dir):
            from laniakea import LocalConfig

            lconf = LocalConfig()
            self._lock_dir = os.path.join(lconf.workspace, 'locks')
            try:
                os.makedirs(self._lock_dir, exist_ok=True)
            except Exception:
                raise Exception(
                    'No suitable location found to place lock file "{}"! - Does a workspace exist with proper permissions?'.format(
                        self._name
                    )
                )

    @property
    def lock_filename(self) -> str:
        return os.path.join(self._lock_dir, 'laniakea_' + self._name + '.lock')

    def acquire(self, raise_error=True) -> bool:
        """
        Try to acquire a lockfile with the given name, useful to ensure only one process is executing a critical
        section at a time.
        :param raise_error: True if we should raise an error, instead of just returning False if lock can't be acquired.
        :return: True if lock was acquired.
        """
        fd = os.open(self.lock_filename, os.O_RDWR | os.O_CREAT)
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            # another instance is running
            self._lock_file_fd = -1
            os.close(fd)
            if raise_error:
                raise Exception(
                    'Unable to acquire lock "{}": Lock held by other instance or thread!'.format(self.lock_filename)
                )
            return False
        self._lock_file_fd = fd
        return True

    def acquire_wait(self):
        if self.acquire(raise_error=False):
            return
        log.info(
            'Waiting on lock "%s". Will continue once the other operation holding the lock has completed.', self._name
        )
        while True:
            time.sleep(5)
            if self.acquire(raise_error=False):
                return

    def release(self):
        """Release an acquired lock. Does nothing if no lock was taken."""
        if self._lock_file_fd <= 0:
            return
        fcntl.lockf(self._lock_file_fd, fcntl.LOCK_UN)
        os.close(self._lock_file_fd)
        self._lock_file_fd = -1


@contextmanager
def process_file_lock(name: str, *, raise_error=True, wait=False):
    flock = ProcessFileLock(name)
    if wait:
        flock.acquire_wait()
    else:
        flock.acquire(raise_error)
    try:
        yield flock
    finally:
        flock.release()


def find_free_port_nr():
    import socket
    from contextlib import closing

    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def ensure_laniakea_master_user(warn_only: bool = False):
    """
    Ensure we are running as Laniakea's "lkmaster" user.
    In case we are root, we try to switch to that user automatically, otherwise we exist
    immediately and ask the user to run the current command again as the proper user.
    """
    import pwd
    import shutil

    from laniakea.localconfig import LocalConfig

    current_username = pwd.getpwuid(os.getuid())[0]
    master_username = LocalConfig().master_user_name
    if current_username == master_username:
        return

    if os.geteuid() == 0 and shutil.which('sudo'):
        os.execvp('sudo', ['sudo', '-u', master_username] + sys.argv)
    else:
        from rich.console import Console

        error_console = Console(stderr=True)
        if warn_only:
            error_console.print(
                '[bold red]IMPORTANT[/]: Running command as user "{}" instead of the expected "{}" user.'.format(
                    current_username, master_username
                )
            )
        else:
            error_console.print('[bold red]ERROR[/]: This command has to be run as user "{}".'.format(master_username))
            sys.exit(6)
