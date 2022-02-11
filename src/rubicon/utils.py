# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os


def safe_rename(src, dst):
    '''
    Instead of directly moving a file with rename(), copy the file
    and then delete the original.
    Also reset the permissions on the resulting copy.
    '''

    from shutil import copy2

    new_fname = copy2(src, dst)
    os.chmod(new_fname, 0o755)
    os.remove(src)
