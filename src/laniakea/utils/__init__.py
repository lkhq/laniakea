# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
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

from lknative import compare_versions
from laniakea.utils.command import run_command, safe_run
from laniakea.utils.arches import arch_matches, any_arch_matches
from laniakea.utils.deb822 import Changes
from laniakea.utils.misc import get_dir_shorthand_for_uuid, random_string, cd, listify, stringify
from laniakea.utils.base64 import encode_base64, decode_base64
from laniakea.utils.json import json_compact_dump

__all__ = ['compare_versions',
           'arch_matches',
           'any_arch_matches',
           'Changes',
           'get_dir_shorthand_for_uuid',
           'random_string',
           'run_command',
           'safe_run',
           'cd',
           'listify',
           'stringify',
           'encode_base64',
           'decode_base64',
           'json_compact_dump']
