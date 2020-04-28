# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

from cylc.flow.batch_sys_handlers.slurm import BATCH_SYS_HANDLER


@pytest.mark.parametrize(
    'job_conf,lines',
    [
        (  # basic
            {
                'batch_system_conf': {},
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': '$HOME/cylc-run/chop/log/job/1/axe/01/job',
                'suite_name': 'chop',
                'task_id': 'axe.1',
            },
            [
                '#SBATCH --job-name=axe.1.chop',
                '#SBATCH --output=cylc-run/chop/log/job/1/axe/01/job.out',
                '#SBATCH --error=cylc-run/chop/log/job/1/axe/01/job.err',
                '#SBATCH --time=3:00',
            ],
        ),
        (  # task name with % character
            {
                'batch_system_conf': {},
                'directives': {},
                'execution_time_limit': 180,
                'job_file_path': (
                    '$HOME/cylc-run/chop/log/job/1/axe%40HEAD/01/job'
                ),
                'suite_name': 'chop',
                'task_id': 'axe%40HEAD.1',
            },
            [
                '#SBATCH --job-name=axe%40HEAD.1.chop',
                (
                    '#SBATCH --output'
                    '=cylc-run/chop/log/job/1/axe%%40HEAD/01/job.out'
                ),
                (
                    '#SBATCH --error'
                    '=cylc-run/chop/log/job/1/axe%%40HEAD/01/job.err'
                ),
                '#SBATCH --time=3:00',
            ],
        ),
        (  # some useful directives
            {
                'batch_system_conf': {},
                'directives': {
                    '-p': 'middle',
                    '--no-requeue': '',
                    '--mem': '256gb',
                },
                'execution_time_limit': 200,
                'job_file_path': '$HOME/cylc-run/chop/log/job/1/axe/01/job',
                'suite_name': 'chop',
                'task_id': 'axe.1',
            },
            [
                '#SBATCH --job-name=axe.1.chop',
                '#SBATCH --output=cylc-run/chop/log/job/1/axe/01/job.out',
                '#SBATCH --error=cylc-run/chop/log/job/1/axe/01/job.err',
                '#SBATCH --time=3:20',
                '#SBATCH -p=middle',
                '#SBATCH --no-requeue',
                '#SBATCH --mem=256gb',
            ],
        ),
    ],
)
def test_format_directives(job_conf: dict, lines: list):
    assert BATCH_SYS_HANDLER.format_directives(job_conf) == lines


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
    assert BATCH_SYS_HANDLER.get_poll_many_cmd(job_ids) == cmd
