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

from cylc.flow.batch_sys_handlers.loadleveler import BATCH_SYS_HANDLER
from cylc.flow.batch_sys_handlers.loadleveler import LoadlevelerHandler


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
                '# @ job_name = chop.axe.1',
                '# @ output = cylc-run/chop/log/job/1/axe/01/job.out',
                '# @ error = cylc-run/chop/log/job/1/axe/01/job.err',
                '# @ wall_clock_limit = 240,180',
                '# @ queue'
            ],
        ),

        (  # some useful directives
            {
                'batch_system_conf': {},
                'directives': {
                    '-q': 'forever',
                    '-V': '',
                    '-l mem': '256gb',
                },
                'execution_time_limit': 180,
                'job_file_path': '$HOME/cylc-run/chop/log/job/1/axe/01/job',
                'suite_name': 'chop',
                'task_id': 'axe.1',
            },
            [
                '# @ job_name = chop.axe.1',
                '# @ output = cylc-run/chop/log/job/1/axe/01/job.out',
                '# @ error = cylc-run/chop/log/job/1/axe/01/job.err',
                '# @ wall_clock_limit = 240,180',
                '# @ -q = forever',
                '# @ -V',
                '# @ -l mem = 256gb',
                '# @ queue'
            ],
        ),
    ],
)
def test_format_directives(job_conf: dict, lines: list):
    assert BATCH_SYS_HANDLER.format_directives(job_conf) == lines


def test_filter_poll_many_output():

    configuration = '''
Id                 Owner      Submitted   ST PRI Class     Running On
----------------   ---------- ----------- -- --- --------  ----------
mars.498.0         brownap     5/20 11:31 R  100 silver    mars
mars.499.0         brownap     5/20 11:31 R  50  No_Class  mars
mars.501.0         brownap     5/20 11:31 I  50  silver
'''
    out = ['Id', '----------------', 'mars.498', 'mars.499', 'mars.501']
    assert LoadlevelerHandler.filter_poll_many_output(configuration) == out
