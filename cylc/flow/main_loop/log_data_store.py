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
"""Log the number and size of each type of object in the data store.

.. note::

   This plugin is for Cylc developers debugging the data store.

If ``matplotlib`` is installed this plugin will plot results as a PDF in
the run directory when the workflow is shut down (cleanly).

"""
import json
from pathlib import Path
from time import time

from cylc.flow.main_loop import (startup, shutdown, periodic)


try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    PLT = True
except ModuleNotFoundError:
    PLT = False

from pympler.asizeof import asizeof


@startup
async def init(scheduler, state):
    """Construct the initial state."""
    state['objects'] = {}
    state['size'] = {}
    state['times'] = []
    for key, _ in _iter_data_store(scheduler.data_store_mgr):
        state['objects'][key] = []
        state['size'][key] = []


@periodic
async def log_data_store(scheduler, state):
    """Count the number of objects and the data store size."""
    state['times'].append(time())
    for key, value in _iter_data_store(scheduler.data_store_mgr):
        if isinstance(value, (list, dict, set)):
            state['objects'][key].append(
                len(value)
            )
        state['size'][key].append(
            asizeof(value)
        )


@shutdown
async def report(scheduler, state):
    """Dump data to JSON, attempt to plot results."""
    _dump(state, scheduler.workflow_run_dir)
    _plot(state, scheduler.workflow_run_dir)


def _iter_data_store(data_store_mgr):
    # the data store itself (for a total measurement)
    yield ('data_store_mgr (total)', data_store_mgr)

    # the top-level attributes of the data store
    for key in dir(data_store_mgr):
        if (
            key != 'data'
            and not key.startswith('__')
            and isinstance(
                value := getattr(data_store_mgr, key),
                (list, dict, set)
            )
        ):
            yield (key, value)

    # the individual components of the "data" attribute
    for datum in data_store_mgr.data.values():
        for key, value in datum.items():
            if key == 'workflow':
                yield (f'data.{key}', [value])
            else:
                yield (f'data.{key}', value)
        # there should only be one workflow in the data store
        break


def _dump(state, path):
    data = {
        'times': state['times'],
        'objects': state['objects'],
        'size': state['size']
    }
    json.dump(
        data,
        Path(path, f'{__name__}.json').open('w+')
    )
    return True


def _plot(state, path, min_size_percent=2):
    if (
        not PLT
        or len(state['times']) < 2
    ):
        return False

    # extract snapshot times
    times = [tick - state['times'][0] for tick in state['times']]

    max_size = max(
        size
        for sizes in state['size'].values()
        for size in sizes
    )

    # filter attributes by the minimum size
    min_size_bytes = max_size * (min_size_percent / 100)
    filtered_keys = {
        key
        for key, sizes in state['size'].items()
        if (
            any(size > min_size_bytes for size in sizes)
            or key.startswith('data.')
        )
    }

    # plot
    fig = plt.figure(figsize=(15, 8))
    ax1 = fig.add_subplot(111)
    fig.suptitle(
        f'data_store_mgr data and attrs above {min_size_percent}% of largest'
        f' (> {int(min_size_bytes / 1000)}kb)'
    )

    # plot sizes
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Size (kb)')
    for key, sizes in state['size'].items():
        if key in filtered_keys:
            ax1.plot(times, [x / 1000 for x in sizes], label=key)

    # plot # objects
    ax2 = ax1.twinx()
    ax2.set_ylabel('Objects')
    for key, objects in state['objects'].items():
        if objects and key in filtered_keys:
            ax2.plot(times, objects, label=key, linestyle=':')

    # legends
    ax1.legend(loc=0)
    ax2.legend(
        (ax1.get_children()[0], ax2.get_children()[0]),
        ('size', 'objects'),
        loc=0
    )

    # start the x-axis at zero
    ax1.set_xlim(0, ax1.get_xlim()[1])

    plt.savefig(
        Path(path, f'{__name__}.pdf')
    )
    return True
