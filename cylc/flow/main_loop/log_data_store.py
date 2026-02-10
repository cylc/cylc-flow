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

from pympler.asizeof import asizeof, Asizer


STORE_OTHER = {
    'added',
    'updated',
}


@startup
async def init(scheduler, state):
    """Construct the initial state."""
    state['objects'] = {}
    state['size'] = {}
    state['times'] = []
    for key, _ in _iter_data_store(scheduler.data_store_mgr.data):
        state['objects'][key] = []
        state['size'][key] = []

    for attr_name in STORE_OTHER:
        state['objects'][attr_name] = []
        state['size'][attr_name] = []

    state['objects']['data_store_mgr'] = []
    state['size']['data_store_mgr'] = []


@periodic
async def log_data_store(scheduler, state):
    """Count the number of objects and the data store size."""
    state['times'].append(time())
    ds = scheduler.data_store_mgr
    for key, value in _iter_data_store(ds.data):
        state['objects'][key].append(
            len(value)
        )
        state['size'][key].append(
            asizeof(value)
        )

    for attr_name in STORE_OTHER:
        attr_value = getattr(ds, attr_name)
        state['objects'][attr_name].append(
            len(attr_value)
        )
        state['size'][attr_name].append(
            asizeof(attr_value)
        )

    asizer = Asizer()
    asizer.exclude_refs(scheduler)
    state['objects']['data_store_mgr'].append(1)
    state['size']['data_store_mgr'].append(asizer.asizeof(ds))


@shutdown
async def report(scheduler, state):
    """Dump data to JSON, attempt to plot results."""
    _dump(state, scheduler.workflow_run_dir)
    _plot(state, scheduler.workflow_run_dir)


def _iter_data_store(data_store):
    for item in data_store.values():
        for key, value in item.items():
            if key == 'workflow':
                yield (key, [value])
            else:
                yield (key, value)
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


def _plot(state, path):
    if (
            not PLT
            or len(state['times']) < 2
    ):
        return False

    times = [tick - state['times'][0] for tick in state['times']]
    _, ax1 = plt.subplots(figsize=(10, 7.5))

    ax1.set_xlabel('Time (s)')

    ax1.set_ylabel('Objects')
    lines = [
        ax1.plot(times, objects, label=key)[0]
        for key, objects in state['objects'].items()
    ]

    ax2 = ax1.twinx()
    ax2.set_ylabel('Size (kb)')
    for sizes in state['size'].values():
        ax2.plot(times, [x / 1000 for x in sizes], linestyle=':')

    ax1.legend(lines, state['objects'], loc=0)
    ax2.legend(
        (ax1.get_children()[0], ax2.get_children()[0]),
        ('objects', 'size'),
        loc=1
    )

    # start the x-axis at zero
    ax1.set_xlim(0, ax1.get_xlim()[1])

    plt.savefig(
        Path(path, f'{__name__}.pdf')
    )
    return True
