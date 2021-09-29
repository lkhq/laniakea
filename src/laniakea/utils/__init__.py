# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from laniakea.utils.command import run_command, safe_run, run_forwarded, safe_run_forwarded
from laniakea.utils.arches import arch_matches, any_arch_matches
from laniakea.utils.deb822 import Changes
from laniakea.utils.misc import get_dir_shorthand_for_uuid, random_string, cd, listify, stringify, \
    is_remote_url, download_file, split_strip, open_compressed
from laniakea.utils.base64 import encode_base64, decode_base64
from laniakea.utils.json import json_compact_dump

__all__ = ['arch_matches',
           'any_arch_matches',
           'Changes',
           'get_dir_shorthand_for_uuid',
           'random_string',
           'run_command',
           'safe_run',
           'run_forwarded',
           'safe_run_forwarded',
           'cd',
           'listify',
           'stringify',
           'is_remote_url',
           'download_file',
           'split_strip',
           'open_compressed',
           'encode_base64',
           'decode_base64',
           'json_compact_dump']
