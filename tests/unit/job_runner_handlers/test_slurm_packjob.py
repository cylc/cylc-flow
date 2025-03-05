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

from cylc.flow.job_runner_handlers.slurm_packjob import JOB_RUNNER_HANDLER


@pytest.mark.parametrize(
    'job_conf,lines',
    [
        (  # heterogeneous job, old-style (packjob)
            {
                'directives': {
                    '-p': 'middle',
                    'packjob_0_--mem': '128gb',
                    'packjob_1_--mem': '256gb',
                },
                'execution_time_limit': 200,
                'job_file_path': 'cylc-run/chop/log/job/1/axe/01/job',
                'workflow_name': 'chop',
                'task_id': '1/axe',
            },
            [
                '#SBATCH --job-name=axe.1.chop',
                (
                    '#SBATCH --output='
                    'cylc-run/chop/log/job/1/axe/01/job.out'
                ),
                (
                    '#SBATCH --error='
                    'cylc-run/chop/log/job/1/axe/01/job.err'
                ),
                '#SBATCH --time=3:20',
                '#SBATCH -p=middle',
                '#SBATCH --mem=128gb',
                '#SBATCH packjob',
                '#SBATCH --mem=256gb',
            ],
        ),

    ],
)
def test_format_directives(job_conf: dict, lines: list):
    assert JOB_RUNNER_HANDLER.format_directives(job_conf) == lines


@pytest.mark.parametrize(
    'job_ids,cmd',
    [
        [['1234567'], ['squeue', '-h', '-j', '1234567']],
        [
            ['1234567', '709394', '30624700'],
            ['squeue', '-h', '-j', '1234567,709394,30624700'],
        ],
    ],
)
def test_get_poll_many_cmd(job_ids: list, cmd: list):
    assert JOB_RUNNER_HANDLER.get_poll_many_cmd(job_ids) == cmd


@pytest.mark.parametrize(
    'out,job_ids',
    [
        [
            """HEADING
1234567  JOB PROPERTIES
709394   JOB PROPERTIES
30624700 JOB PROPERTIES
""", ['1234567', '30624700', '709394'],
        ],
        [
            """HEADING
1234567+0 JOB PROPERTIES (HETERO)
1234567+1 JOB PROPERTIES (HETERO)
709394    JOB PROPERTIES
30624700  JOB PROPERTIES
""", ['1234567', '30624700', '709394'],
        ],
    ],
)
def test_filter_poll_many_output(job_ids: list, out: str):
    assert sorted(JOB_RUNNER_HANDLER.filter_poll_many_output(out)) == job_ids
