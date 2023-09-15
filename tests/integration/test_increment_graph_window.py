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

from contextlib import suppress

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.data_store_mgr import (
    TASK_PROXIES,
)


async def test_increment_graph_window_blink(flow, scheduler, start):
    """Test with a task which drifts in and out of the n-window.

    This workflow presents a fiendish challenge for the graph window algorithm.

    The test runs in the n=3 window and simulates running each task in the
    chain a - s one by one. The task "blink" is dependent on multiple tasks
    in the chain awkwardly spaced so that the "blink" task routinely
    disappears from the n-window, only to re-appear again later.

    The expansion of the window around the "blink" task is difficult to get
    right as it can be influenced by caches from previous graph walks.
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': '1',
            'graph': {
                'R1': '''
                    # the "abdef" chain of tasks which run one after another
                    a => b => c => d => e => f => g => h => i => j => k => l =>
                    m => n => o => p => q => r => s

                    # these dependencies cause "blink" to disappear and
                    # reappear at set intervals
                    a => blink
                    g => blink
                    m => blink
                    s => blink
                ''',
            }
        }
    })
    schd = scheduler(id_)

    def increment_graph_window(task):
        """Increment the graph window about the active task."""
        nonlocal schd
        tokens = schd.tokens.duplicate(cycle='1', task=task)
        schd.data_store_mgr.increment_graph_window(
            tokens,
            IntegerPoint('1'),
            {1},
            is_manual_submit=False,
        )

    async def get_n_window():
        """Read out the graph window of the workflow."""
        nonlocal schd
        await schd.update_data_structure()
        data = schd.data_store_mgr.data[schd.data_store_mgr.workflow_id]
        return {
            t.name: t.graph_depth
            for t in data[TASK_PROXIES].values()
        }

    async def complete_task(task):
        """Mark a task as completed."""
        nonlocal schd
        schd.data_store_mgr.remove_pool_node(task, IntegerPoint('1'))
        await schd.update_data_structure()

    def add_task(task):
        """Add a waiting task to the pool."""
        schd.data_store_mgr.add_pool_node(task, IntegerPoint('1'))

    # the tasks traversed via the "blink" task when...
    blink = {
        1: {
            # the blink task is n=1
            'blink': 1,
            'a': 2,
            'g': 2,
            'm': 2,
            's': 2,
            'b': 3,
            'f': 3,
            'h': 3,
            'l': 3,
            'n': 3,
            'r': 3,
        },
        2: {
            # the blink task is n=2
            'blink': 2,
            'a': 3,
            'g': 3,
            'm': 3,
            's': 3,
        },
        3: {
            # the blink task is n=3
            'blink': 3,
        },
        4: {
            # the blink task is n=4
        },
    }

    def advance():
        """Advance to the next task in the workflow.

        This works its way down the chain of tasks between "a" and "s"
        inclusive, yielding what the n-window should look like for this
        workflow at each step.

        Yields:
            tuple - (previous_task, active_task, n_window)

            previous_task:
                The task which has just "succeeded".
            active_task:
                The task which is about to run.
            n_window:
                Dictionary of {task_name: graph_depth} for the n=3 window.

        """
        # the initial window on startup (minus the nodes traversed via "blink")
        window = {
            'a': 0,
            'b': 1,
            'c': 2,
            'd': 3,
        }
        # the tasks we will run in order
        letters = 'abcdefghijklmnopqrs'
        # the graph-depth of the "blink" task at each stage of the workflow
        blink_distances = [1] + (list((*range(2, 5), *range(3, 0, -1))) * 3)

        for ind, blink_distance in zip(range(len(letters)), blink_distances):
            previous_task = letters[ind - 1] if ind > 0 else None
            active_task = letters[ind]
            yield (
                previous_task,
                active_task,
                {
                    # the tasks traversed via the "blink" task
                    **blink[blink_distance],
                    # the tasks in the main "abcdefg" chain
                    **{key: abs(value) for key, value in window.items()},
                }
            )

            # move each task in the "abcdef" chain down one
            window = {key: value - 1 for key, value in window.items()}
            # add the n=3 task in the "abcdef" chain into the window
            with suppress(IndexError):
                window[letters[ind + 4]] = 3
            # pull out anything which is not supposed to be in the n=3 window
            window = {
                key: value
                for key, value in window.items()
                if abs(value) < 4
            }

    async with start(schd):
        schd.data_store_mgr.set_graph_window_extent(3)
        await schd.update_data_structure()

        for previous_task, active_task, n_window in advance():
            # mark the previous task as completed
            await complete_task(previous_task)
            # add the next task to the pool
            add_task(active_task)
            # run the graph window algorithm
            increment_graph_window(active_task)
            # compare the result to what we were expecting
            assert await get_n_window() == n_window
