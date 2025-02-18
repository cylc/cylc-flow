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

import pytest

from cylc.flow.job_runner_handlers.pbs import (
    JOB_RUNNER_HANDLER,
    PBSHandler
)
from cylc.flow.job_runner_mgr import JobRunnerManager


VERY_LONG_STR = 'x' * 240


@pytest.mark.parametrize(
    'job_conf,lines',
    [
        pytest.param(
            {
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
                'platform': {
                    'job runner': 'pbs',
                    'job name length maximum': 100
                }
            },
            [
                '#PBS -N axe.1.chop',
                '#PBS -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#PBS -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#PBS -l walltime=180',
            ],
            id='basic'
        ),
        pytest.param(
            {
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': VERY_LONG_STR,
                'platform': {
                    'job runner': 'pbs',
                }
            },
            [
                '#PBS -N '
                f'None.{VERY_LONG_STR[:PBSHandler.JOB_NAME_LEN_MAX - 5]}',
                '#PBS -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#PBS -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#PBS -l walltime=180',
            ],
            id='long-job-name'
        ),
        pytest.param(
            {
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
                'platform': {
                    'job runner': 'pbs',
                    'job name length maximum': 6
                }
            },
            [
                '#PBS -N axe.1.',
                '#PBS -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#PBS -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#PBS -l walltime=180',
            ],
            id='truncate-job-name'
        ),
        pytest.param(
            {
                'directives': {
                    '-q': 'forever',
                    '-V': '',
                    '-l mem': '256gb',
                },
                'execution_time_limit': 180,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
                'platform': {
                    'job runner': 'pbs',
                    'job name length maximum': 100
                }
            },
            [
                '#PBS -N axe.1.chop',
                '#PBS -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#PBS -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#PBS -l walltime=180',
                '#PBS -q forever',
                '#PBS -V',
                '#PBS -l mem=256gb',
            ],
            id='custom-directives'
        ),
    ],
)
def test_format_directives(job_conf: dict, lines: list):
    assert JOB_RUNNER_HANDLER.format_directives(job_conf) == lines


def test_filter_poll_many_output():
    """It should strip trailing junk from job IDs.

    Job IDs are assumed to be a series of numbers, optionally followed by a
    full-stop and some other letters and numbers which are not needed for
    job tracking purposes.

    Job IDs are not expected to start with letters e.g. `abc.456` is not
    supported.
    """
    assert JOB_RUNNER_HANDLER.filter_poll_many_output('''
Job id            Name             User              Time Use S Queue
----------------  ---------------- ----------------  -------- - -----
12345.foo.bar.baz test-pbs         xxxxxxx                  0 Q reomq
23456.foo         test-pbs         xxxxxxx                  0 Q romeq
34567             test-pbs         xxxxxxx                  1 Q romeq
abc.456           test-pbs         xxxxxxx                  2 Q romeq
abcdef            test-pbs         xxxxxxx                  2 Q romeq
    ''') == ['12345', '23456', '34567']


def test_filter_submit_output(tmp_path):
    """See notes for test_filter_poll_many_output."""
    status_file = tmp_path / 'submit_out'
    status_file.touch()

    def test(out):
        return JobRunnerManager._filter_submit_output(
            status_file,
            JOB_RUNNER_HANDLER,
            out,
            '',
        )[2]

    assert test('   12345.foo.bar.baz') == '12345'
    assert test('   12345.foo') == '12345'
    assert test('   12345') == '12345'
