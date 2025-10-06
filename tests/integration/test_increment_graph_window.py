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
from cylc.flow.id import Tokens


def increment_graph_window(schd, task):
    """Increment the graph window about the active task."""
    tokens = schd.tokens.duplicate(cycle='1', task=task)
    schd.data_store_mgr.increment_graph_window(
        tokens,
        IntegerPoint('1'),
        is_manual_submit=False,
    )


def get_deltas(schd):
    """Return the ids and graph-window values in the delta store.

    Note, call before get_n_window as this clears the delta store.

    Returns:
        (added, updated, pruned)

    """
    # populate added deltas
    schd.data_store_mgr.gather_delta_elements(
        schd.data_store_mgr.added,
        'added',
    )
    # populate pruned deltas
    schd.data_store_mgr.prune_data_store()
    # Run depth finder
    schd.data_store_mgr.window_depth_finder()
    # populate updated deltas
    schd.data_store_mgr.gather_delta_elements(
        schd.data_store_mgr.updated,
        'updated',
    )
    return (
        {
            # added
            Tokens(tb_task_proxy.id)['task']: tb_task_proxy.graph_depth
            for tb_task_proxy in schd.data_store_mgr.deltas[TASK_PROXIES].added
        },
        {
            # updated
            Tokens(tb_task_proxy.id)['task']: tb_task_proxy.graph_depth
            for tb_task_proxy in schd.data_store_mgr.deltas[
                TASK_PROXIES
            ].updated
            # only include those updated nodes whose depths have been set
            if 'graph_depth'
            in {sub_field.name for sub_field, _ in tb_task_proxy.ListFields()}
        },
        {
            # pruned
            Tokens(id_)['task']
            for id_ in schd.data_store_mgr.deltas[TASK_PROXIES].pruned
        },
    )


async def get_n_window(schd):
    """Read out the graph window of the workflow."""
    await schd.update_data_structure()
    data = schd.data_store_mgr.data[schd.data_store_mgr.workflow_id]
    return {
        t.name: t.graph_depth
        for t in data[TASK_PROXIES].values()
    }


async def complete_task(schd, task):
    """Mark a task as completed."""
    schd.data_store_mgr.remove_pool_node(task, IntegerPoint('1'))


def add_task(schd, task):
    """Add a waiting task to the pool."""
    schd.data_store_mgr.add_pool_node(task, IntegerPoint('1'))


def get_graph_walk_cache(schd):
    """Return the head task names of cached graph walks."""
    # prune graph walk cache
    schd.data_store_mgr.prune_data_store()
    # fetch the cached walks
    n_window_node_walks = sorted(
        Tokens(task_id)['task']
        for task_id in schd.data_store_mgr.n_window_node_walks
    )
    n_window_completed_walks = sorted(
        Tokens(task_id)['task']
        for task_id in schd.data_store_mgr.n_window_completed_walks
    )
    # the IDs in set and keys of dict are only the same at n<2 window.
    assert n_window_node_walks == n_window_completed_walks
    return n_window_completed_walks


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
        blink_distances = [1] + [*range(2, 5), *range(3, 0, -1)] * 3

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

        previous_n_window = {}
        for previous_task, active_task, expected_n_window in advance():
            # mark the previous task as completed
            await complete_task(schd, previous_task)
            # add the next task to the pool
            add_task(schd, active_task)
            # run the graph window algorithm
            increment_graph_window(schd, active_task)
            # get the deltas which increment_graph_window created
            added, updated, pruned = get_deltas(schd)

            # compare the n-window in the store to what we were expecting
            n_window = await get_n_window(schd)
            assert n_window == expected_n_window

            # compare the deltas to what we were expecting
            if active_task != 'a':
                # skip the first task as this is complicated by startup logic
                assert added == {
                    key: value
                    for key, value in expected_n_window.items()
                    if key not in previous_n_window
                }
                # Skip added as depth isn't updated
                # (the manager only updates those that need it)
                assert updated == {
                    key: value
                    for key, value in expected_n_window.items()
                    if key not in added
                }
                assert pruned == {
                    key
                    for key in previous_n_window
                    if key not in expected_n_window
                }

            previous_n_window = n_window


async def test_window_resize_rewalk(flow, scheduler, start):
    """The window resize method should wipe and rebuild the n-window."""
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true',
        },
        'scheduling': {
            'graph': {
                'R1': 'a => b => c => d => e => f => g'
            }
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        # start with an empty pool
        schd.pool.remove(schd.pool.get_tasks()[0])

        # the n-window should be empty
        assert await get_n_window(schd) == {}

        # expand the window around 1/d
        add_task(schd, 'd')
        increment_graph_window(schd, 'd')

        # set the graph window to n=3
        schd.data_store_mgr.set_graph_window_extent(3)
        assert set(await get_n_window(schd)) == {
            'a', 'b', 'c', 'd', 'e', 'f', 'g'
        }

        # set the graph window to n=1
        schd.data_store_mgr.set_graph_window_extent(1)
        schd.data_store_mgr.window_resize_rewalk()
        assert set(await get_n_window(schd)) == {
            'c', 'd', 'e'
        }

        # set the graph window to n=2
        schd.data_store_mgr.set_graph_window_extent(2)
        schd.data_store_mgr.window_resize_rewalk()
        assert set(await get_n_window(schd)) == {
            'b', 'c', 'd', 'e', 'f'
        }


async def test_cache_pruning(flow, scheduler, start):
    """It should remove graph walks from the cache when no longer needed.

    The algorithm caches graph walks for efficiency. This test is designed to
    ensure we don't introduce a memory leak by failing to clear cached walks
    at the correct point.
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': '''
                    # a chain of tasks
                    a => b1 & b2 => c => d1 & d2 => e => f
                    # force "a" to drift into an out of the window
                    a => c
                    a => e
                '''
            }
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        schd.data_store_mgr.set_graph_window_extent(1)

        # work through this workflow, step by step checking the cached items...

        # active: a
        add_task(schd, 'a')
        increment_graph_window(schd, 'a')
        assert get_graph_walk_cache(schd) == ['a']

        # active: b1, b2
        await complete_task(schd, 'a')
        add_task(schd, 'b1')
        add_task(schd, 'b2')
        increment_graph_window(schd, 'b1')
        increment_graph_window(schd, 'b2')
        assert get_graph_walk_cache(schd) == ['a', 'b1', 'b2']

        # active: c
        await complete_task(schd, 'b1')
        await complete_task(schd, 'b2')
        add_task(schd, 'c')
        increment_graph_window(schd, 'c')
        assert get_graph_walk_cache(schd) == ['a', 'b1', 'b2', 'c']

        # active: d1, d2
        await complete_task(schd, 'c')
        add_task(schd, 'd1')
        add_task(schd, 'd2')
        increment_graph_window(schd, 'd1')
        increment_graph_window(schd, 'd2')
        assert get_graph_walk_cache(schd) == ['c', 'd1', 'd2']

        # active: e
        await complete_task(schd, 'd1')
        await complete_task(schd, 'd2')
        add_task(schd, 'e')
        increment_graph_window(schd, 'e')
        assert get_graph_walk_cache(schd) == ['d1', 'd2', 'e']

        # active: f
        await complete_task(schd, 'e')
        add_task(schd, 'f')
        increment_graph_window(schd, 'f')
        assert get_graph_walk_cache(schd) == ['e', 'f']

        # active: None
        await complete_task(schd, 'f')
        increment_graph_window(schd, 'f')
        assert get_graph_walk_cache(schd) == []
