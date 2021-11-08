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
"""Resets the list of bad hosts.

The scheduler stores a set of hosts which it has been unable to contact to
save contacting these hosts again.

This list is cleared if a task cannot be submitted because all of the hosts it
might use cannot be reached.

If a task succeeds in submitting a job on the second host it tries, then the
first host remains in the set of unreachable (bad) hosts, even though the
failure might have been transitory. For this reason, this plugin periodically
clears the set.

Suggested interval - an hour.
"""

from cylc.flow.main_loop import periodic


@periodic
async def reset_bad_hosts(scheduler, _):
    """Empty bad_hosts."""
    scheduler.task_events_mgr.reset_bad_hosts()
