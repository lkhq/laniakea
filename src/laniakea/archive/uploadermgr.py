# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import ArchiveUploader
from laniakea.logging import archive_log
from laniakea.utils.gpg import delete_gpg_key, import_keyfile, list_gpg_fingerprints


def import_key_file_for_uploader(uploader: ArchiveUploader, fname: T.PathUnion):
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
    archive_log.info('UPLOADER-ADDED-GPG: %s: %s', uploader.email, ', '.join(fingerprints))


def retrieve_uploader_fingerprints() -> list[str]:
    """List all fingerprints for keys that have archive upload access."""

    lconf = LocalConfig()
    keyring_dir = lconf.uploaders_keyring_dir
    os.makedirs(keyring_dir, exist_ok=True)

    return list_gpg_fingerprints(keyring_dir)


def delete_uploader_key(fingerprint: str):
    """Remove a fingerprint from the uploader keyring.."""

    lconf = LocalConfig()
    keyring_dir = lconf.uploaders_keyring_dir
    os.makedirs(keyring_dir, exist_ok=True)

    delete_gpg_key(keyring_dir, fingerprint)
    archive_log.info('UPLOADER-REMOVED-GPG: %s', fingerprint)
