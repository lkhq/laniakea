# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import ArchiveUploader
from laniakea.logging import log, archive_log
from laniakea.utils.gpg import delete_gpg_key, import_keyfile, list_gpg_fingerprints
from laniakea.utils.deb822 import split_maintainer_field
from laniakea.archive.changes import Changes


class UploaderError(Exception):
    """Issue with an uploader."""


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


def guess_archive_uploader_for_changes(session, changes: Changes) -> ArchiveUploader:
    """Try to find an uploader user who uploaded the respective changes file.

    :param session: SQLAlchemy session.
    :param changes: A Changes file instance.
    :return: The archive uploader. Raises an error if none was found.
    """

    possible_uploaders: list[ArchiveUploader] = (
        session.query(ArchiveUploader).filter(ArchiveUploader.pgp_fingerprints.any(changes.primary_fingerprint)).all()
    )
    if not possible_uploaders:
        raise UploaderError(
            'Unable to find registered uploader for fingerprint "{}" for "{}"'.format(
                changes.primary_fingerprint, changes.filename
            )
        )
    uploader = None
    if len(possible_uploaders) == 1:
        uploader = possible_uploaders[0]
    else:
        # A GPG signature may be shared by multiple uploaders, this is especially common for package build machines.
        # In such events, we try to guess the right uploader, but fall back to picking the first one in case that fails.
        # FIXME: This will cause issues with uploader-specific permissions, but in case those are used we should likely
        # expect each uploader to have their own GPG key
        changed_by = changes.changes.get('Changed-By', None)
        if changed_by:
            _, _, email = split_maintainer_field(changed_by)
            for u in possible_uploaders:
                if u.email == email:
                    uploader = u
                    break
        if not uploader:
            uploader = possible_uploaders[0]
        log.info('More than one possible uploader found for `%s`, picked `%s`', changes.filename, uploader.email)

    return uploader
