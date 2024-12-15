# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2023 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


from laniakea.db import (
    Job,
    JobStatus,
    StatsEntry,
    PackageType,
    SpearsExcuse,
    BinaryPackage,
    DebcheckIssue,
    SourcePackage,
    StatsEventKind,
    ArchiveRepository,
    SoftwareComponent,
    ArchiveArchitecture,
    SpearsMigrationTask,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
    session_scope,
    make_stats_key,
    make_stats_key_jobqueue,
)


def _latest_stat_value_for(session, key: str) -> int | None:
    """Get the latest value for a particular key."""

    result = (
        session.query(StatsEntry.value)
        .filter(
            StatsEntry.key == key,
        )
        .order_by(StatsEntry.time.desc())
        .first()
    )
    if not result:
        return None
    return result[0]


def _add_stat_value_if_changed(session, key: str, value: int):
    """Add a new statistics entry if there was a change."""
    last_val = _latest_stat_value_for(session, key)
    if last_val is None or last_val != value:
        session.add(StatsEntry(key, value))


def _collect_package_counts(session, rss: ArchiveRepoSuiteSettings):
    """Collect statistics about the registered packages."""

    # count binary packages
    for arch in rss.suite.architectures:
        key = make_stats_key(StatsEventKind.BIN_PKG_COUNT, rss.repo, rss.suite, arch)
        bpkg_count = (
            session.query(BinaryPackage.uuid)
            .filter(
                BinaryPackage.repo_id == rss.repo_id,
                BinaryPackage.suites.any(id=rss.suite_id),
                BinaryPackage.architecture_id == arch.id,
            )
            .distinct(BinaryPackage.name)
            .count()
        )
        _add_stat_value_if_changed(session, key, bpkg_count)

    # count source packages
    key = make_stats_key(StatsEventKind.SRC_PKG_COUNT, rss.repo, rss.suite)
    spkg_count = (
        session.query(SourcePackage.uuid)
        .filter(SourcePackage.repo_id == rss.repo_id, SourcePackage.suites.any(id=rss.suite_id))
        .distinct(SourcePackage.name)
        .count()
    )
    _add_stat_value_if_changed(session, key, spkg_count)


def _collect_swcpts_counts(session, repo: ArchiveRepository):
    """Collect statistics about software components."""

    key = make_stats_key(StatsEventKind.SOFTWARE_COMPONENTS, repo, None)
    cpt_count = (
        session.query(SoftwareComponent.uuid)
        .filter(SoftwareComponent.pkgs_binary.any(repo_id=repo.id))
        .distinct(SoftwareComponent.cid)
        .count()
    )
    _add_stat_value_if_changed(session, key, cpt_count)


def _collect_depcheck_issue_counts(session, rss: ArchiveRepoSuiteSettings):
    """Collect statistics about DebCheck issues."""

    # count source packages
    key = make_stats_key(StatsEventKind.DEPCHECK_ISSUES_SRC, rss.repo, rss.suite)
    dci_count = (
        session.query(DebcheckIssue.uuid)
        .filter(
            DebcheckIssue.package_type == PackageType.SOURCE,
            DebcheckIssue.repo_id == rss.repo_id,
            DebcheckIssue.suite_id == rss.suite_id,
        )
        .count()
    )
    _add_stat_value_if_changed(session, key, dci_count)

    # count binary packages
    for arch in rss.suite.architectures:
        key = make_stats_key(StatsEventKind.DEPCHECK_ISSUES_BIN, rss.repo, rss.suite, arch)
        dci_count = (
            session.query(DebcheckIssue.uuid)
            .filter(
                DebcheckIssue.package_type == PackageType.BINARY,
                DebcheckIssue.repo_id == rss.repo_id,
                DebcheckIssue.suite_id == rss.suite_id,
                DebcheckIssue.architectures.contains([arch.name]),
            )
            .count()
        )
        _add_stat_value_if_changed(session, key, dci_count)


def _collect_migration_excuse_counts(session):
    """Collect statistics about Migration Excuses."""

    for mtask in session.query(SpearsMigrationTask).all():
        excuses_count = session.query(SpearsExcuse.uuid).filter(SpearsExcuse.migration_id == mtask.id).count()
        key = make_stats_key(StatsEventKind.MIGRATIONS_PENDING, mtask.repo, mtask.target_suite)
        _add_stat_value_if_changed(session, key, excuses_count)


def _collect_job_queue_stats(session):
    """Collect statistics about Migration Excuses."""

    for arch in session.query(ArchiveArchitecture).all():
        arch_name = 'any' if arch.name == 'all' else arch.name

        depwait_count = (
            session.query(Job.uuid).filter(Job.status == JobStatus.DEPWAIT, Job.architecture == arch_name).count()
        )
        key = make_stats_key_jobqueue(StatsEventKind.JOB_QUEUE_DEPWAIT, arch_name)
        _add_stat_value_if_changed(session, key, depwait_count)

        pending_count = (
            session.query(Job.uuid)
            .filter(
                Job.status.in_([JobStatus.WAITING, JobStatus.SCHEDULED, JobStatus.STARVING]),
                Job.architecture == arch_name,
            )
            .count()
        )
        key = make_stats_key_jobqueue(StatsEventKind.JOB_QUEUE_PENDING, arch_name)
        _add_stat_value_if_changed(session, key, pending_count)


def _collect_new_queue_stats(session, rss: ArchiveRepoSuiteSettings):
    """Collect statistics about packages pending human review."""

    key = make_stats_key(StatsEventKind.REVIEW_QUEUE_LENGTH, rss.repo, rss.suite)
    pending_count = (
        session.query(ArchiveQueueNewEntry.id)
        .filter(
            ArchiveQueueNewEntry.package.has(repo_id=rss.repo_id), ArchiveQueueNewEntry.destination_id == rss.suite_id
        )
        .count()
    )
    _add_stat_value_if_changed(session, key, pending_count)


def task_collect_statistics(registry):
    """Collect measurements for statistics."""

    with session_scope() as session:
        _collect_migration_excuse_counts(session)
        _collect_job_queue_stats(session)

        repos = set()
        for rss in session.query(ArchiveRepoSuiteSettings).all():
            repos.add(rss.repo)
            _collect_package_counts(session, rss)
            _collect_depcheck_issue_counts(session, rss)
            _collect_new_queue_stats(session, rss)

        for repo in repos:
            _collect_swcpts_counts(session, repo)
