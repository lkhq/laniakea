# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import Union
from pathlib import Path

from laniakea import LocalConfig
from laniakea.db import ArchiveUploader
from laniakea.utils.gpg import import_keyfile


def import_key_file_for_uploader(uploader: ArchiveUploader, fname: Union[Path, str]):
    """Import a new GPG key from a file for the respective uploader."""

    lconf = LocalConfig()
    keyring_dir = lconf.uploaders_keyring_dir
    os.makedirs(keyring_dir, exist_ok=True)

    fingerprints = import_keyfile(keyring_dir, fname)
    if not uploader.pgp_fingerprints:
        uploader.pgp_fingerprints = []
    for fpr in fingerprints:
        if fpr not in uploader.pgp_fingerprints:
            uploader.pgp_fingerprints.append(fpr)
