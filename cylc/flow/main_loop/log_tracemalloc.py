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

"""Profile Cylc with tracemalloc.

This takes tracemalloc snapshots periodically.

Snapshots are written into "~/cylc-run/<workflow>/tracemalloc/", to load them
for analysis, run:

  tracemalloc.Snapshot.load('.../path/to/x.tracemalloc')

The memory diffs are written to stdout.
"""

from pathlib import Path
import tracemalloc

from cylc.flow import LOG
from cylc.flow.main_loop import periodic, shutdown, startup


@startup
async def init(scheduler, state):
    """Create the state object on startup."""
    tracemalloc.start()
    state['out_dir'] = Path(scheduler.workflow_run_dir, 'tracemalloc')
    state['out_dir'].mkdir()
    logfile = state['out_dir'] / 'log'
    state['log'] = logfile.open('w+')
    state['itt'] = 0
    LOG.warning(f'Writing tracemalloc output to {logfile}')


@periodic
async def take_snapshot(scheduler, state, diff_filter='cylc/', max_length=20):
    """Take a memory snapshot and compare it to the previous one.

    Args:
        scheduler:
            Unused in this plugin.
        state:
            The state object initialised in "init".
        diff_filter:
            If supplied, only changes containing this string will be displayed.
            Used to restrict reporting to items which contain Cylc file paths.
        max_length:
            The top "max_length" items will be displayed with each summary.

    """
    # take a snapshot
    new = tracemalloc.take_snapshot()

    # dump the snapshot to the filesystem
    new.dump(state['out_dir'] / f'{state["itt"]}.tracemalloc')

    # compare this snapshot to the previous one
    if state.get('prev'):
        # generate a list of the things which have changed
        cmp = [
            item
            for item in new.compare_to(state['prev'], 'lineno')
            # filter for the libraries we are interested in
            if not diff_filter or diff_filter in str(item)
        ]

        # print a summary of the memory change
        print('+/-', sum(stat.size_diff for stat in cmp), file=state['log'])

        # report the individual  changes
        for stat in sorted(cmp, key=lambda x: x.size_diff, reverse=True)[
            :max_length
        ]:
            if stat.size_diff != 0:
                print(f'  {stat}', file=state['log'])
        print('', file=state['log'])

    state['prev'] = new
    state['itt'] += 1
    state['log'].flush()


@shutdown
async def close_log(scheduler, state):
    """Close the log file on shutdown."""
    state['log'].close()
