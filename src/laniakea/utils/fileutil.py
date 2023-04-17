# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import shutil
from contextlib import contextmanager

import laniakea.typing as T

# Match safe filenames
re_file_safe = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.~+-]*$')

# Match safe filenames, including slashes
re_file_safe_slash = re.compile(r'^[a-zA-Z0-9][/a-zA-Z0-9_.~+-]*$')


def check_filename_safe(fname: T.PathUnion) -> bool:
    """Check if a filename contains only safe characters"""
    if not re_file_safe.match(str(fname)):
        return False
    return True


def check_filepath_safe(path: T.PathUnion) -> bool:
    """Check if a filename contains only safe characters"""
    if not re_file_safe_slash.match(str(path)):
        return False
    return True


def hardlink_or_copy(src: T.PathUnion, dst: T.PathUnion, *, override: bool = True):
    """Hardlink a file :src to :dst or copy the file in case linking is not possible"""

    try:
        os.link(src, dst)
    except FileExistsError as e:
        if not override:
            raise e
        os.unlink(dst)
        hardlink_or_copy(src, dst, override=override)
    except (PermissionError, OSError):
        shutil.copy2(src, dst)
        shutil.chown(dst, user=os.getuid(), group=os.getgid())


def safe_rename(src: T.PathUnion, dst: T.PathUnion, *, override: bool = False):
    '''
    Instead of directly moving a file with rename(), copy the file
    and then delete the original.
    Also reset the permissions on the resulting copy.
    '''

    from shutil import copy2

    if override and os.path.isfile(dst):
        os.unlink(dst)
    new_fname = copy2(src, dst)
    os.chmod(new_fname, 0o755)
    os.unlink(src)


@contextmanager
def open_compressed(fname, mode='rb'):
    '''
    Open a few compressed filetypes easily.
    '''

    lower_fname = fname.lower()
    f = None
    if lower_fname.endswith('.xz'):
        import lzma

        f = lzma.open(fname, mode=mode)
    elif lower_fname.endswith('.gz'):
        import gzip

        f = gzip.open(fname, mode=mode)
    else:
        raise Exception('Can not decompress file (compression type not recognized): {}'.format(fname))

    try:
        yield f
    finally:
        f.close()
