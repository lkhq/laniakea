# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from pathlib import Path

import laniakea.typing as T
from laniakea.db import ArchiveRepository
from laniakea.utils import safe_rename
from laniakea.archive import UploadHandler
from laniakea.msgstream import EventEmitter
from laniakea.archive.changes import parse_changes

from .rubiconfig import RubiConfig


def safe_move_rejected_upload(conf: RubiConfig, changes_fname: T.PathUnion) -> T.Optional[str]:
    """Safely moves a changes file and its data out of the incoming queue into the reject queue.
    This function must not throw an error, and instead return its error as string.
    """

    changes_basedir = os.path.dirname(changes_fname)
    try:
        changes = parse_changes(changes_fname, require_signature=False)
        files = changes.files
        for file in files.values():
            fname = os.path.join(changes_basedir, file.fname)
            if os.path.exists(fname):
                safe_rename(fname, os.path.join(conf.rejected_dir, file.fname), override=True)
        safe_rename(changes_fname, os.path.join(conf.rejected_dir, os.path.basename(changes_fname)), override=True)
    except Exception as move_e:
        return str(move_e)
    return None


def handle_package_upload(
    session,
    conf: RubiConfig,
    uh: UploadHandler,
    changes_fname: T.PathUnion,
):
    """
    Handle an upload of a package.
    """

    reject_info_fname = os.path.join(conf.rejected_dir, Path(changes_fname).stem + '.reason')
    os.makedirs(conf.rejected_dir, exist_ok=True)

    try:
        upload_result = uh.process_changes(changes_fname)
    except Exception as e:
        # we got an error that we can't attribute to an uploader, so we couldn't even consider this upload
        error_msg = str(e)
        move_e = safe_move_rejected_upload(conf, changes_fname)
        if move_e:
            error_msg += '\nAnother error occurred while moving files: ' + move_e
        with open(reject_info_fname, 'w', encoding='utf-8') as f:
            f.write(error_msg + '\n')
        uh.emit_package_upload_rejected(changes_fname, error_msg, None)
        return

    # the package upload was considered, but rejected anyway
    if upload_result.error or not upload_result.success:
        move_e = safe_move_rejected_upload(conf, changes_fname)
        if move_e:
            upload_result.error += '\nAnother error occurred while moving files: ' + move_e
        with open(reject_info_fname, 'w', encoding='utf-8') as f:
            f.write(upload_result.error + '\n')
        uh.emit_package_upload_rejected(changes_fname, upload_result.error, upload_result.uploader)
        return

    # if we're here, the new package was accepted - the UploadHandler will have handled
    # sending the announcement message


def handle_package_uploads(
    session, conf: RubiConfig, repo: ArchiveRepository, changes_files: T.Sequence[T.PathUnion], event_emitter: EventEmitter
):
    """
    Handle upload of packages.
    """

    uh = UploadHandler(session, repo, event_emitter)
    uh.keep_source_packages = False
    uh.auto_emit_reject = False

    for fname in changes_files:
        handle_package_upload(session, conf, uh, fname)
