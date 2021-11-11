# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import toml
import logging as log
from laniakea import LocalConfig, get_config_file


class RubiConfig():
    '''
    Local configuration for Rubicon.
    '''

    log_storage_dir = None
    rejected_dir = None

    isotope_root_dir = None

    trusted_gpg_keyrings: list[str] = []

    def __init__(self, local_config=None):
        if not local_config:
            local_config = LocalConfig()
        self._lconf = local_config
        self._loaded = False

        # try to load default configuration
        self.load()

    def load_from_file(self, fname):

        cdata = {}
        if os.path.isfile(fname):
            with open(fname) as json_file:
                cdata = toml.load(json_file)

        self.log_storage_dir = cdata.get('LogStorage', None)
        if not self.log_storage_dir:
            raise Exception('No "LogStorage" entry in Rubicon configuration: We need to know where to store log files.')

        self.rejected_dir = cdata.get('RejectedDir', None)
        if not self.rejected_dir:
            raise Exception('No "RejectedDir" entry in Rubicon configuration: We need to know where to place rejected files.')

        self.trusted_gpg_keyrings = cdata.get('TrustedGpgKeyringDir', [])
        if not self.trusted_gpg_keyrings or type(self.trusted_gpg_keyrings) != list:
            self.trusted_gpg_keyrings = self._lconf.trusted_gpg_keyrings
            if not self.trusted_gpg_keyrings:
                log.error('No trusted GPG keyrings were found. Ensure "TrustedGpgKeyringDir" entry in the general configuration is set properly.')

        self.isotope_root_dir = cdata.get('IsotopeRootDir', None)

        self._loaded = True

    def load(self):
        fname = get_config_file('rubicon.toml')
        if fname:
            self.load_from_file(fname)
        else:
            raise Exception('Unable to find Rubicon configuration (usually in `/etc/laniakea/rubicon.toml`')
