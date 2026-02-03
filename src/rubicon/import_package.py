# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import subprocess
from pathlib import Path

import laniakea.typing as T
from laniakea.db import SourcePackage, ArchiveRepository
from laniakea.utils import safe_rename
from laniakea.archive import UploadHandler
from laniakea.logging import log
from laniakea.msgstream import EventEmitter
from laniakea.archive.utils import repo_suite_settings_for
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
) -> tuple[SourcePackage | None, str | None]:
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
        return None, None

    # the package upload was considered, but rejected anyway
    if upload_result.error or not upload_result.success:
        move_e = safe_move_rejected_upload(conf, changes_fname)
        if move_e:
            upload_result.error += '\nAnother error occurred while moving files: ' + move_e
        with open(reject_info_fname, 'w', encoding='utf-8') as f:
            f.write(upload_result.error + '\n')
        uh.emit_package_upload_rejected(changes_fname, upload_result.error, upload_result.uploader)
        return None, None

    # if we're here, the new package was accepted - the UploadHandler will have handled
    # sending the announcement message

    # return the source package if it isn't in the NEW queue
    return None if upload_result.is_new else upload_result.spkg, upload_result.target_suite_name


def handle_package_uploads(
    session,
    conf: RubiConfig,
    repo: ArchiveRepository,
    changes_files: T.Sequence[T.PathUnion],
    event_emitter: EventEmitter,
):
    """
    Handle upload of packages.
    """

    from laniakea.ariadne import schedule_package_builds_for_source

    uh = UploadHandler(repo, event_emitter)
    uh.keep_source_packages = False
    uh.auto_emit_reject = False

    new_in_repo: dict[str, list[SourcePackage]] = {}
    for fname in changes_files:
        spkg, target_suite_name = handle_package_upload(session, conf, uh, fname)
        if spkg:
            if target_suite_name not in new_in_repo:
                new_in_repo[target_suite_name] = []
            new_in_repo[target_suite_name].append(spkg)

    if not conf.schedule_builds:
        return

    if new_in_repo and conf.lk_archive_exe:
        for suite_name in new_in_repo.keys():
            # quickly publish the new source packages in affected suites
            proc = subprocess.run(
                [conf.lk_archive_exe, 'publish', '--only-sources', '--repo', repo.name, '--suite', suite_name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                check=False,
            )
            if proc.returncode != 0:
                log.error(
                    'Unable to fast-publish source data for %s:%s: %s', repo.name, suite_name, str(proc.stdout, 'utf-8')
                )
                # we just exit here - Ariadne will pick up the missing build jobs on its next housekeeping run
                return

    for suite_name in new_in_repo.keys():
        rss = repo_suite_settings_for(session, repo.name, suite_name)
        for spkg in new_in_repo[suite_name]:
            schedule_package_builds_for_source(
                session,
                rss,
                spkg,
                simulate=False,
            )
