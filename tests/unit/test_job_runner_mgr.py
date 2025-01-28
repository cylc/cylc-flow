# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from cylc.flow.job_runner_mgr import JobRunnerManager

jrm = JobRunnerManager()


SAMPLE_STATUS = """
ignore me, I have no = sign
CYLC_JOB_RUNNER_NAME=pbs
CYLC_JOB_ID=2361713
CYLC_JOB_RUNNER_SUBMIT_TIME=2025-01-28T14:46:04Z
CYLC_JOB_PID=2361713
CYLC_JOB_INIT_TIME=2025-01-28T14:46:05Z
CYLC_MESSAGE=2025-01-28T14:46:05Z|INFO|sleep 31
CYLC_JOB_RUNNER_EXIT_POLLED=2025-01-28T14:46:08Z
CYLC_JOB_EXIT=SUCCEEDED
CYLC_JOB_EXIT_TIME=2025-01-28T14:46:38Z
"""


def test__job_poll_status_files(tmp_path):
    """Good Path: A valid job.status files exists"""
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'job.status').write_text(SAMPLE_STATUS)
    ctx = jrm._jobs_poll_status_files(str(tmp_path), 'sub')
    assert ctx.job_runner_name == 'pbs'
    assert ctx.job_id == '2361713'
    assert ctx.job_runner_exit_polled == 1
    assert ctx.pid == '2361713'
    assert ctx.time_submit_exit == '2025-01-28T14:46:04Z'
    assert ctx.time_run == '2025-01-28T14:46:05Z'
    assert ctx.time_run_exit == '2025-01-28T14:46:38Z'
    assert ctx.run_status == 0
    assert ctx.messages == ['2025-01-28T14:46:05Z|INFO|sleep 31']


def test__job_poll_status_files_task_failed(tmp_path):
    """Good Path: A valid job.status files exists"""
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'job.status').write_text("CYLC_JOB_EXIT=FOO")
    ctx = jrm._jobs_poll_status_files(str(tmp_path), 'sub')
    assert ctx.run_status == 1
    assert ctx.run_signal == 'FOO'


def test__job_poll_status_files_deleted_logdir():
    """The log dir has been deleted whilst the task is still active.
    Return the context with the message that the task has failed.
    """
    ctx = jrm._jobs_poll_status_files('foo', 'bar')
    assert ctx.run_signal == 'ERR/Job files have been removed'
    assert ctx.run_status == 1


def test__job_poll_status_files_ioerror(tmp_path, capsys):
    """There is no readable file.
    """
    (tmp_path / 'sub').mkdir()
    jrm._jobs_poll_status_files(str(tmp_path), 'sub')
    cap = capsys.readouterr()
    assert '[Errno 2] No such file or directory' in cap.err

