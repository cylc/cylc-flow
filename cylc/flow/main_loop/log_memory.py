# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
import json
import math
from pathlib import Path
from time import time

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    PLT = True
except ModuleNotFoundError:
    PLT = False

from pympler.asizeof import asized


# TODO: make this configurable in the global config
MIN_SIZE = 10000


async def before(scheduler, state):
    """Take an initial memory snapshot."""
    state['data'] = []
    await during(scheduler, state)


async def during(scheduler, state):
    """Take a memory snapshot"""
    state['data'].append((
        time(),
        _compute_sizes(scheduler, min_size=MIN_SIZE)
    ))


async def after(scheduler, state):
    """Take a final memory snapshot."""
    await during(scheduler, state)
    _dump(state['data'], scheduler.suite_run_dir)
    fields, times = _transpose(state['data'])
    _plot(
        fields,
        times,
        scheduler.suite_run_dir,
        f'cylc.flow.scheduler.Scheduler attrs > {MIN_SIZE / 1000}kb'
    )


def _compute_sizes(obj, min_size=10000):
    """Return the sizes of the attributes of an object."""
    size = asized(obj, detail=2)
    for ref in size.refs:
        if ref.name == '__dict__':
            break
    else:
        raise Exception('Cannot find __dict__ reference')

    return {
        item.name.split(':')[0][4:]: item.size
        for item in ref.refs
        if item.size > min_size
    }


def _transpose(data):
    """Pivot data from snapshot to series oriented."""
    all_keys = set()
    for _, datum in data:
        all_keys.update(datum.keys())

    # sort keys by the size of the last checkpoint so that the fields
    # get plotted from largest to smallest
    all_keys = list(all_keys)
    all_keys.sort(key=lambda x: data[-1][1].get(x, 0), reverse=True)

    # extract data for each field, if not present 
    fields = {}
    for key in all_keys:
        fields[key] = [
            datum.get(key, -1)
            for _, datum in data
        ]

    start_time = data[0][0]
    times = [
        timestamp - start_time
        for timestamp, _ in data
    ]

    return fields, times


def _dump(data, path):
    json.dump(
        data,
        Path(path, f'{__name__}.json').open('w+')
    )
    return True


def _plot(fields, times, path, title='Objects'):
    if (
            not PLT
            or len(times) < 2
    ):
        return False

    fig, ax1 = plt.subplots(figsize=(10, 7.5))

    fig.suptitle(title)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Memory (kb)')

    for key, sizes in fields.items():
        ax1.plot(times, [x / 1000 for x in sizes], label=key)

    ax1.legend(loc=0)

    # start both axis at 0
    ax1.set_xlim(0, ax1.get_xlim()[1])
    ax1.set_ylim(0, ax1.get_ylim()[1])

    plt.savefig(
        Path(path, f'{__name__}.pdf')
    )
    return True
