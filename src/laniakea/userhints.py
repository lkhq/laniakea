# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import glob

import tomlkit

import laniakea.typing as T
from laniakea.db import (
    SpearsHint,
    SynchrotronConfig,
    SynchrotronSource,
    SyncBlacklistEntry,
    SpearsMigrationTask,
    session_scope,
)
from laniakea.git import Git
from laniakea.logging import log
from laniakea.localconfig import LocalConfig, UserHintReposConfig


class UserHintsError(Exception):
    """Error while reading user hints data."""


class UserHints:
    def __init__(self):
        lconf = LocalConfig()
        hrconf = UserHintReposConfig()
        self._git_url = hrconf.user_hints_git_url
        self._repo_root = os.path.join(lconf.workspace, 'user-hints-source')
        self._manifest = None

    def update(self):
        """Update user hints from their Git repository."""
        if not self._git_url:
            return

        log.debug('Updating user hints Git repository copy')
        repo = Git(self._repo_root)
        repo.clone_or_pull(self._git_url)

    def load(self, update: bool = False):
        """Load user hints data."""
        if not self._git_url:
            return
        if self._manifest:
            return

        log.info('Updating user hints and overrides from Git')
        if update:
            self.update()

        manifest_fname = os.path.join(self._repo_root, "laniakea.toml")
        if not os.path.isfile(manifest_fname):
            log.warning("Unable to load user hints: Repository %s has no Laniakea manifest file.", self._git_url)

        with open(manifest_fname, 'r') as f:
            self._manifest = tomlkit.load(f)

    def _find_config_files_for_path_hint(self, path_hint: str) -> list[T.PathUnion]:
        """Find configuration files for a manifest path hint."""

        path = os.path.join(self._repo_root, path_hint)
        if os.path.isfile(path):
            return [path]
        else:
            return list(glob.glob(os.path.join(path, '*.toml')))

    def update_synchrotron_blacklists(self):
        """Update Synchrotron blacklist entries based on the user hints."""

        with session_scope() as session:
            for repo_name, repo_udata in self._manifest.items():
                synchrotron_d = repo_udata.get('synchrotron')
                if not synchrotron_d:
                    continue
                bl_manifests = synchrotron_d.get('blacklists')
                if not bl_manifests:
                    continue

                for bl_manifest in bl_manifests:
                    sync_origin = (
                        session.query(SynchrotronSource)
                        .filter(
                            SynchrotronSource.os_name == bl_manifest['from_os'],
                            SynchrotronSource.suite_name == bl_manifest['from_suite'],
                        )
                        .one_or_none()
                    )
                    if not sync_origin:
                        log.warning(
                            'User Hints: No Synchrotron source found for OS %s and suite %s',
                            bl_manifest['from_os'],
                            bl_manifest['from_suite'],
                        )
                        continue

                    sync_conf = (
                        session.query(SynchrotronConfig)
                        .filter(
                            SynchrotronConfig.repo.has(name=repo_name),
                            SynchrotronConfig.source_id == sync_origin.id,
                            SynchrotronConfig.destination_suite.has(name=bl_manifest['to']),
                        )
                        .one_or_none()
                    )
                    if not sync_conf:
                        log.warning(
                            'User Hints: No Synchrotron configuration found for origin OS %s/%s to target %s',
                            bl_manifest['from_os'],
                            bl_manifest['from_suite'],
                            bl_manifest['to'],
                        )
                        continue

                    bl_index = {}
                    bl_entries_all = (
                        session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.config_id == sync_conf.id).all()
                    )
                    for entry in bl_entries_all:
                        bl_index[entry.pkgname] = entry

                    bl_files = self._find_config_files_for_path_hint(bl_manifest['path'])
                    valid_files_found = False
                    for fname in bl_files:
                        with open(fname, 'r') as f:
                            data = tomlkit.load(f)
                            if 'ignore' not in data:
                                log.warning('User Hints: Missing \'issues\' key in %s', os.path.basename(fname))
                                continue

                            valid_files_found = True
                            for uentry in data['ignore']:
                                # update reason for existing entry if we have one
                                e = bl_index.pop(uentry[0], None)
                                if e:
                                    e.reason = uentry[1]
                                    continue

                                # we have a new blacklist entry
                                e = SyncBlacklistEntry()
                                e.config = sync_conf
                                e.pkgname = uentry[0]
                                e.reason = uentry[1]
                                session.add(e)

                    # delete entries that no longer exist, but only if we had valid files
                    # (this is a sanity check, so we don't accidentally drop everything)
                    if valid_files_found:
                        for entry in bl_index.values():
                            session.delete(entry)

    def update_spears_hints(self):
        """Update Britney hints based on user commands."""

        with session_scope() as session:
            for repo_name, repo_udata in self._manifest.items():
                spears_d = repo_udata.get('spears')
                if not spears_d:
                    continue
                hints_manifests = spears_d.get('hints')
                if not hints_manifests:
                    continue

                for manifest in hints_manifests:
                    mtask_candidates = (
                        session.query(SpearsMigrationTask)
                        .filter(
                            SpearsMigrationTask.repo.has(name=repo_name),
                            SpearsMigrationTask.target_suite.has(name=manifest['to']),
                        )
                        .all()
                    )
                    mtask = None
                    for mt in mtask_candidates:
                        if mt.source_suites_str == manifest['from']:
                            mtask = mt
                            break
                    if not mtask:
                        log.warning(
                            'User Hints: No Spears configuration found for migration %s -> %s',
                            manifest['from'],
                            manifest['to'],
                        )
                        continue

                    hints_index = {}
                    hints_all = session.query(SpearsHint).filter(SpearsHint.migration_id == mtask.id).all()
                    for hint in hints_all:
                        hints_index[hint.hint] = hint

                    hint_files = self._find_config_files_for_path_hint(manifest['path'])
                    valid_files_found = False
                    for fname in hint_files:
                        with open(fname, 'r') as f:
                            data = tomlkit.load(f)
                            if 'hints' not in data:
                                log.warning('User Hints: Missing \'hints\' key in %s', os.path.basename(fname))
                                continue

                            valid_files_found = True
                            for hentry in data['hints']:
                                britney_hint = '{}/{}'.format(hentry[0], hentry[1])
                                reason = ''
                                if len(hentry) >= 3:
                                    reason = hentry[3]

                                # update reason for existing hint if we have one
                                hint = hints_index.pop(britney_hint, None)
                                if hint:
                                    hint.reason = reason
                                    continue

                                # we have a new Britney hint
                                hint = SpearsHint()
                                hint.migration_task = mtask
                                hint.hint = britney_hint
                                hint.reason = reason
                                session.add(hint)

                    # delete entries that no longer exist, but only if we had valid files
                    # (this is a sanity check, so we don't accidentally drop everything)
                    if valid_files_found:
                        for hint in hints_index.values():
                            session.delete(hint)
