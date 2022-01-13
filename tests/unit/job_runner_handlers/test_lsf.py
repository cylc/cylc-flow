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

from cylc.flow.job_runner_handlers.lsf import JOB_RUNNER_HANDLER


@pytest.mark.parametrize(
    'job_conf,lines',
    [
        (  # basic
            {
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
            },
            [
                '#BSUB -J axe.1.chop',
                '#BSUB -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#BSUB -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#BSUB -W 3',
            ],
        ),
        (  # some useful directives
            {
                'directives': {
                    '-q': 'forever',
                    '-B': '',
                    '-ar': '',
                },
                'execution_time_limit': 200,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
            },
            [
                '#BSUB -J axe.1.chop',
                '#BSUB -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#BSUB -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#BSUB -W 4',
                '#BSUB -q forever',
                '#BSUB -B',
                '#BSUB -ar',
            ],
        ),
    ],
)
def test_format_directives(job_conf: dict, lines: list):
    assert JOB_RUNNER_HANDLER.format_directives(job_conf) == lines


def test_get_submit_stdin():
    outs = JOB_RUNNER_HANDLER.get_submit_stdin(__file__, None)
    assert outs[0].name == __file__
    assert outs[1] is None
