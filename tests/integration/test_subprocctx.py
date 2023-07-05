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
"""Tests involving the Cylc Subprocess Context Object
"""

import asyncio
from cylc.flow import logging


async def test_log_xtrigger_stdout(flow, scheduler, run_dir, run):
    """Output from xtriggers should appear in the scheduler log:

    (As per the toy example in the Cylc Docs)
    """
    # Setup a workflow:
    reg = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'graph': {'R1': '@myxtrigger => foo'},
            'xtriggers': {'myxtrigger': 'myxtrigger()'}
        }
    })
    # Create an xtrigger:
    xt_lib = run_dir / reg / 'lib/python/myxtrigger.py'
    xt_lib.parent.mkdir(parents=True, exist_ok=True)
    xt_lib.write_text(
        "from sys import stderr\n\n\n"
        "def myxtrigger():\n"
        "    print('Hello World')\n"
        "    print('Hello Hades', file=stderr)\n"
        "    return True, {}"
    )
    schd = scheduler(reg)
    async with run(schd, level=logging.DEBUG) as log:
        # Set off check for x-trigger:
        schd.xtrigger_mgr.call_xtriggers_async(
            schd.pool.get_tasks()[0])

        # Wait on the main-loop until the xtrigger has finished:
        xt_complete = False
        while not xt_complete:
            xt_complete = schd.xtrigger_mgr._get_xtrigs(
                schd.pool.get_tasks()[0])[0][3]
            await asyncio.sleep(1)

        # Assert that both stderr and out from the print statement
        # in our xtrigger appear in the log.
        for expected in ['Hello World', 'Hello Hades']:
            assert any(expected in i.message for i in log.records)
