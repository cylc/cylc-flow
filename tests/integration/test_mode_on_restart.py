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
"""What happens to the mode on restart?
"""

import pytest

from cylc.flow.exceptions import InputError
from cylc.flow.scheduler import Scheduler
from cylc.flow.run_modes import RunMode


MODES = [('live'), ('simulation'), ('dummy')]


@pytest.mark.parametrize('mode_after', MODES)
@pytest.mark.parametrize('mode_before', MODES + [None])
async def test_restart_mode(
    flow, run, scheduler, start, one_conf,
    mode_before, mode_after
):
    """Restarting a workflow in live mode leads to workflow in live mode.

    N.B - we need use run becuase the check in question only happens
    on start.
    """
    schd: Scheduler
    id_ = flow(one_conf)
    schd = scheduler(id_, run_mode=mode_before)
    async with start(schd):
        if not mode_before:
            mode_before = 'live'
        assert schd.get_run_mode().value == mode_before

    schd = scheduler(id_, run_mode=mode_after)

    if (
        mode_before == mode_after
        or not mode_before and mode_after != 'live'
    ):
        # Restarting in the same mode is fine.
        async with run(schd):
            assert schd.get_run_mode().value == mode_before
    else:
        # Restarting in a new mode is not:
        errormsg = f'^This.*{mode_before} mode: You.*{mode_after} mode.$'
        with pytest.raises(InputError, match=errormsg):
            async with run(schd):
                pass
