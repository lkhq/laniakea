# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import shutil
from datetime import UTC, datetime

import pytest
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent

import lkscheduler.sdaemon as sdaemon
from mirk.messages import message_templates
from lkscheduler.sdaemon import TaskError, JobsRegistry, SchedulerDaemon, run_task_tool


def _python_cmd(code: str) -> list[str]:
    return [sys.executable, '-c', code]


def test_run_task_tool():
    assert run_task_tool('Test', _python_cmd('print("All good.")')) is None

    # we want the last line of the output in the summary, as that usually contains the error message
    error = run_task_tool(
        'Spears',
        _python_cmd(
            'import sys\n'
            'print("Traceback (most recent call last):", file=sys.stderr)\n'
            'print("  File \\"<string>\\", line 1, in <module>", file=sys.stderr)\n'
            'print("KeyError: BPID(pkg/1.0/arm64)", file=sys.stderr)\n'
            'print(file=sys.stderr)\n'
            'sys.exit(3)\n'
        ),
    )
    assert error == 'Spears failed with exit code 3: KeyError: BPID(pkg/1.0/arm64)'

    error = run_task_tool('Rubicon', _python_cmd('import sys; sys.exit(1)'))
    assert error == 'Rubicon failed with exit code 1: No output.'


def test_run_task_tool_output_order(caplog):
    """Output on stdout and stderr has to be logged in the order it was written."""

    error = run_task_tool(
        'Spears',
        _python_cmd(
            'import sys\n'
            'print("Running migration...")\n'
            'print("Traceback (most recent call last):", file=sys.stderr)\n'
            'print("KeyError: BPID(pkg/1.0/arm64)", file=sys.stderr)\n'
            'print("Migration failed.")\n'
            'sys.exit(1)\n'
        ),
    )
    assert error == 'Spears failed with exit code 1: Migration failed.'
    assert caplog.messages == [
        'Spears: Error: Running migration...\n'
        'Traceback (most recent call last):\n'
        'KeyError: BPID(pkg/1.0/arm64)\n'
        'Migration failed.\n'
    ]


def test_failed_task_raises(monkeypatch):
    """Failed tasks must not be reported as having executed successfully (#58)."""

    class StubConfig:
        rubicon_exe = shutil.which('true')
        synchrotron_exe = shutil.which('false')

    monkeypatch.setattr(sdaemon, 'SchedulerConfig', StubConfig)

    sdaemon.task_rubicon_scan(JobsRegistry())
    with pytest.raises(TaskError, match='^Synchrotron Autosync failed with exit code 1: No output.$'):
        sdaemon.task_synchrotron_autosync(JobsRegistry())


def test_failed_task_announcement():
    """A failed task has to emit an event that Mirk can display."""

    class StubJob:
        name = 'Migrate packages between suites'

    class StubScheduler:
        def get_job(self, job_id):
            assert job_id == 'spears-migrate'
            return StubJob()

    class StubEmitter:
        def __init__(self):
            self.events = []

        def submit_event(self, subject, data):
            self.events.append((subject, data))

    daemon = SchedulerDaemon.__new__(SchedulerDaemon)
    daemon._scheduler = StubScheduler()
    daemon._emitter = StubEmitter()

    def make_error_event(exception):
        return JobExecutionEvent(EVENT_JOB_ERROR, 'spears-migrate', 'default', datetime.now(UTC), exception=exception)

    daemon._on_job_error(make_error_event(TaskError('Spears failed with exit code 1: KeyError: <module>')))
    daemon._on_job_error(make_error_event(ValueError('Something unexpected happened')))

    assert daemon._emitter.events == [
        (
            'task-failed',
            {
                'job_id': 'spears-migrate',
                'job_name': 'Migrate packages between suites',
                'reason': 'Spears failed with exit code 1: KeyError: <module>',
            },
        ),
        (
            'task-failed',
            {
                'job_id': 'spears-migrate',
                'job_name': 'Migrate packages between suites',
                'reason': 'ValueError: Something unexpected happened',
            },
        ),
    ]

    # check how Mirk renders the event, the raw tool output must not end up being interpreted as HTML
    tag = '_lk.scheduler.task-failed'
    text = message_templates[tag](tag, dict(daemon._emitter.events[0][1]))
    assert text == (
        'Scheduled task <b>Migrate packages between suites</b> has <font color="#da4453">failed</font>: '
        '<code>Spears failed with exit code 1: KeyError: &lt;module&gt;</code>'
    )
