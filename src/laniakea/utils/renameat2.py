# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
# Copyright (c) 2021 Jordan Webb
#
# SPDX-License-Identifier: LGPL-3.0+ or MIT

import os
from enum import IntFlag
from ctypes import CDLL, get_errno
from pathlib import Path
from contextlib import contextmanager

import laniakea.typing as T

glibc = CDLL('libc.so.6', use_errno=True)

__all__ = ['exchange_paths', 'Flags']


class Flags(IntFlag):
    """Bit flags accepted by the ``flags`` parameter of :func:`renameat2.renameat2`"""

    RENAME_EXCHANGE = 2
    """
    Atomically exchange oldpath and newpath. Both pathnames must exist but may be of
    different types (e.g., one could be a non-empty directory and the other a symbolic
    link).
    RENAME_EXCHANGE can't be used in combination with RENAME_NOREPLACE or
    RENAME_WHITEOUT.
    """

    RENAME_NOREPLACE = 1
    """
    Don't overwrite newpath of the rename. Return an error if newpath already exists.
    RENAME_NOREPLACE requires support from the underlying filesystem. See the
    :manpage:`renameat(2)` manpage for more information.
    """

    RENAME_WHITEOUT = 4
    """
    Specifying RENAME_WHITEOUT creates a "whiteout" object at the source of the rename
    at the same time as performing the rename. The whole operation is atomic, so that
    if the rename succeeds then the whiteout will also have been created.
    This operation makes sense only for overlay/union filesystem implementations.
    See the :manpage:`renameat(2)` man page for more information.
    """


def renameat2_raw(olddirfd: int, oldpath: str, newdirfd: int, newpath: str, flags: Flags = Flags(0)) -> None:
    """
    Wrapper for the raw renameat2 syscall wrapper in GLibc.
    """
    r: int = glibc.renameat2(olddirfd, oldpath.encode(), newdirfd, newpath.encode(), flags)
    if r != 0:
        errn = get_errno()
        raise OSError(errn, 'renameat2 failed: {}'.format(os.strerror(errn)))


@contextmanager
def _split_dirfd(path: T.PathUnion):
    path = Path(path)
    fd = os.open(path.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        yield (fd, path.name)
    finally:
        os.close(fd)


def rename(
    oldpath: T.PathUnion,
    newpath: T.PathUnion,
    replace: bool = True,
    whiteout: bool = False,
) -> None:
    """Rename a file using the renameat2 system call.
    :param oldpath: Path to the file to rename
    :type oldpath: Union[pathlib.Path, str]
    :param newpath: Path to rename the file to
    :type newpath: Union[pathlib.Path, str]
    :param replace: If true, any existing file at newpath will be replaced.
      If false, any existing file at newpath will cause an error to be raised.
      False corresponds to passing RENAME_NOREPLACE to the system call.
    :type replace: bool
    :param whiteout: If true, a "whiteout" file will be left behind at oldpath.
      True corresponds to passing RENAME_WHITEOUT to the system call.
    :type whiteout: bool
    :raises OSError: if the system call fails
    """
    flags = Flags(0)
    if not replace:
        flags |= Flags.RENAME_NOREPLACE

    if whiteout:
        flags |= Flags.RENAME_WHITEOUT

    with _split_dirfd(oldpath) as (dirfd_a, name_a):
        with _split_dirfd(newpath) as (dirfd_b, name_b):
            renameat2_raw(dirfd_a, name_a, dirfd_b, name_b, flags)


def exchange_paths(a: T.PathUnion, b: T.PathUnion) -> None:
    """Atomically swap two files.
    This is probably the main attraction of this module.
    After this call, the file originally referred to by the first path
    will be referred to by the second, and the file originally referred
    to by the second path will be referred to by the first.
    This is an atomic operation; that is to say, there is no possible
    intermediate state where the files could be "partially" swapped;
    either the call succeeds and the files are exchanged, or the call
    fails and the files are not exchanged.
    This function is implemented by passing RENAME_EXCHANGE to the system call.
    :param a: Path to a file
    :type a: Union[pathlib.Path, str]
    :param b: Path to a file
    :type b: Union[pathlib.Path, str]
    :raises OSError: if `a` and `b` cannot be swapped
    """
    with _split_dirfd(a) as (dirfd_a, name_a):
        with _split_dirfd(b) as (dirfd_b, name_b):
            renameat2_raw(dirfd_a, name_a, dirfd_b, name_b, Flags.RENAME_EXCHANGE)
