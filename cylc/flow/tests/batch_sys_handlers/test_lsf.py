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

from cylc.flow.batch_sys_handlers.lsf import BATCH_SYS_HANDLER


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
                '#BSUB -J axe.1.chop',
                '#BSUB -o cylc-run/chop/log/job/1/axe/01/job.out',
                '#BSUB -e cylc-run/chop/log/job/1/axe/01/job.err',
                '#BSUB -W 3',
            ],
        ),
        (  # some useful directives
            {
                'batch_system_conf': {},
                'directives': {
                    '-q': 'forever',
                    '-B': '',
                    '-ar': '',
                },
                'execution_time_limit': 200,
                'job_file_path': '$HOME/cylc-run/chop/log/job/1/axe/01/job',
                'suite_name': 'chop',
                'task_id': 'axe.1',
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
    assert BATCH_SYS_HANDLER.format_directives(job_conf) == lines


def test_get_submit_stdin():
    outs = BATCH_SYS_HANDLER.get_submit_stdin(__file__, None)
    assert outs[0].name == __file__
    assert outs[1] is None
