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

+--------------------+--------+-------+-------+
| ↓restart \ start → | live   | sim   | dummy |
+====================+========+=======+=======+
| live               | live   | sim * | ???   |
| sim                | live * | sim   | ???   |
| dummy              | ???    | ???   | dummy |
+--------------------+--------+-------+-------+

* A warning ought to be emitted, since the user doesn't otherwise know
  what's happening.
"""

import pytest


@pytest.mark.parametrize('mode_before', (('live'), ('simulation')))
@pytest.mark.parametrize('mode_after', (('live'), ('simulation')))
async def test_restart_mode(
    flow, scheduler, start, one_conf, mode_before, mode_after
):
    """Restarting a workflow in live mode leads to workflow in live mode
    """
    id_ = flow(one_conf)
    schd = scheduler(id_, run_mode=mode_before)
    async with start(schd):
        assert schd.config.run_mode() == mode_before

    schd.options.run_mode = mode_after
    async with start(schd):
        assert schd.config.run_mode() == mode_before
