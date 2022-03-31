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
"""Main loop plugin for monitoring main loop plugins.

.. note::

   This plugin is for Cylc developers debugging main loop operations.

If ``matplotlib`` is installed this plugin will plot results as a PDF in
the run directory when the workflow is shut down (cleanly).

"""
from collections import deque
import json
from pathlib import Path

from cylc.flow.main_loop import startup, shutdown

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    PLT = True
except ModuleNotFoundError:
    PLT = False


@startup
async def init(scheduler, _):
    """Override default queue length of 1.

    This allows timings to accumulate, normally only the most recent is kept.
    """
    plugins = scheduler.main_loop_plugins
    for plugin in plugins['timings']:
        plugins['timings'][plugin] = deque()


@shutdown
async def report(scheduler, _):
    """Extract plugin function timings."""
    data = scheduler.main_loop_plugins['timings']
    if data:
        data = _normalise(data)
        _dump(data, scheduler.workflow_run_dir)
        _plot(data, scheduler.workflow_run_dir)


def _normalise(data):
    earliest_time = min((
        start_time
        for _, timings in data.items()
        for start_time, duration in timings
    ))
    return {
        plugin_name: [
            (start_time - earliest_time, duration)
            for start_time, duration in timings
        ]
        for (plugin_name, _), timings in data.items()
    }


def _dump(data, path):
    json.dump(
        data,
        Path(path, f'{__name__}.json').open('w+'),
        indent=4
    )
    return True


def _plot(data, path):
    if not PLT:
        return False

    _, ax1 = plt.subplots(figsize=(10, 7.5))
    ax1.set_xlabel('Workflow Run Time (s)')
    ax1.set_ylabel('XTrigger Run Time (s)')

    for plugin_name, (timings) in data.items():
        x_data = []
        y_data = []
        for start_time, duration in timings:
            x_data.append(start_time)
            y_data.append(duration)
        ax1.scatter(x_data, y_data, label=plugin_name)

    ax1.set_xlim(0, ax1.get_xlim()[1])
    ax1.set_ylim(0, ax1.get_ylim()[1])

    ax1.legend()
    plt.savefig(
        Path(path, f'{__name__}.pdf')
    )
    return True
