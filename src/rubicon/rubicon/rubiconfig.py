# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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

import os
import json
import logging as log
from laniakea import LocalConfig, get_config_file


class RubiConfig():
    '''
    Local configuration for Rubicon.
    '''

    log_storage_dir = None
    rejected_dir = None

    isotope_root_dir = None

    trusted_gpg_keyrings = []

    def __init__(self, local_config=None):
        if not local_config:
            local_config = LocalConfig()
        self._lconf = local_config
        self._loaded = False

        # try to load default configuration
        self.load()

    def load_from_file(self, fname):

        jdata = {}
        if os.path.isfile(fname):
            with open(fname) as json_file:
                jdata = json.load(json_file)

        self.log_storage_dir = jdata.get('LogStorage', None)
        if not self.log_storage_dir:
            raise Exception('No "LogStorage" entry in Rubicon configuration: We need to know where to store log files.')

        self.rejected_dir = jdata.get('RejectedDir', None)
        if not self.rejected_dir:
            raise Exception('No "RejectedDir" entry in Rubicon configuration: We need to know where to place rejected files.')

        self.trusted_gpg_keyrings = jdata.get('TrustedGpgKeyringDir', [])
        if not self.trusted_gpg_keyrings or type(self.trusted_gpg_keyrings) != list:
            self.trusted_gpg_keyrings = self._lconf.trusted_gpg_keyrings
            if not self.trusted_gpg_keyrings:
                log.error('No trusted GPG keyrings were found. Ensure "TrustedGpgKeyringDir" entry in the general configuration is set properly.')

        self.isotope_root_dir = jdata.get('IsotopeRootDir', None)

        self._loaded = True

    def load(self):
        fname = get_config_file('rubicon.json')
        if fname:
            self.load_from_file(fname)
        else:
            raise Exception('Unable to find Rubicon configuration (usually in `/etc/laniakea/rubicon.json`')
