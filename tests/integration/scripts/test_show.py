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

import json
import pytest
import re
from types import SimpleNamespace

from colorama import init as colour_init

from cylc.flow.id import Tokens
from cylc.flow.scripts.show import (
    show,
)


RE_STATE = re.compile('state:.*')


@pytest.fixture(scope='module')
def mod_my_conf():
    """A workflow configuration with some workflow metadata."""
    return {
        'meta': {
            'title': 'Workflow Title',
            'description': """
                My
                multiline
                description.
            """,
            'URL': 'http://ismycomputerturnedon.com/',
            'answer': '42',
        },
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        },
        'runtime': {
            'foo': {
                'meta': {
                    'title': 'Task Title',
                    'description': '''
                        Task
                        multiline
                        description
                    ''',
                    'URL': (
                        'http://hasthelargehadroncollider'
                        'destroyedtheworldyet.com/'
                    ),
                    'question': 'mutually exclusive',
                },
            },
        },
    }


@pytest.fixture(scope='module')
async def mod_my_schd(mod_flow, mod_scheduler, mod_start, mod_my_conf):
    """A "started" workflow."""
    id_ = mod_flow(mod_my_conf)
    schd = mod_scheduler(id_)
    async with mod_start(schd):
        yield schd


async def test_workflow_meta_query(mod_my_schd, capsys):
    """It should fetch workflow metadata."""
    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        list_prereqs=False,
        task_defs=None,
    )

    # plain output
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        'title: Workflow Title',
        'description: My',
        'multiline',
        'description.',
        'answer: 42',
        'URL: http://ismycomputerturnedon.com/',
    ]

    # json output
    opts.json = True
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'title': 'Workflow Title',
        'description': 'My\nmultiline\ndescription.',
        'answer': '42',
        'URL': 'http://ismycomputerturnedon.com/',
    }


async def test_task_meta_query(mod_my_schd, capsys):
    """It should fetch task metadata."""
    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        list_prereqs=False,
        task_defs=['foo'],
    )

    # plain output
    ret = await show(
        mod_my_schd.workflow,
        None,
        opts,
    )
    assert ret == 0
    out, err = capsys.readouterr()

    assert out.splitlines() == [
        'title: Task Title',
        'question: mutually exclusive',
        'description: Task',
        'multiline',
        'description',
        'URL: http://hasthelargehadroncolliderdestroyedtheworldyet.com/',
    ]

    # json output
    opts.json = True
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'foo': {
            'title': 'Task Title',
            'question': 'mutually exclusive',
            'description': 'Task\nmultiline\ndescription',
            'URL': 'http://hasthelargehadroncolliderdestroyedtheworldyet.com/',
        }
    }


async def test_task_instance_query(
    flow, scheduler, start, capsys
):
    """It should fetch task instance data, sorted by task name."""

    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        task_defs=None,
        list_prereqs=False,
    )
    schd = scheduler(
        flow(
            {
                'scheduling': {
                    'graph': {'R1': 'zed & dog & cat & ant'},
                },
            },
        ),
        paused_start=False,
    )
    async with start(schd):
        await schd.update_data_structure()
        ret = await show(
            schd.workflow,
            [Tokens('//1/*')],
            opts,
        )
        assert ret == 0

    out, _ = capsys.readouterr()
    assert [
        line for line in out.splitlines()
        if line.startswith("Task ID")
    ] == [  # results should be sorted
        'Task ID: 1/ant',
        'Task ID: 1/cat',
        'Task ID: 1/dog',
        'Task ID: 1/zed',
    ]


@pytest.mark.parametrize(
    'workflow_run_mode, run_mode_info',
    (
        ('live', 'Skip'),
        ('dummy', 'Dummy'),
        ('simulation', 'Simulation'),
    )
)
@pytest.mark.parametrize(
    'attributes_bool, flow_nums, expected_state, expected_flows',
    [
        pytest.param(
            False, [1], 'state: waiting (run mode={})', None,
        ),
        pytest.param(
            True,
            [1, 2],
            'state: waiting (held,queued,runahead,run mode={})',
            'flows: [1,2]',
        )
    ]
)
async def test_task_instance_state_flows(
    flow, scheduler, start, capsys,
    workflow_run_mode, run_mode_info,
    attributes_bool, flow_nums, expected_state, expected_flows
):
    """It should print task instance state, attributes, and flows."""

    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        task_defs=None,
        list_prereqs=False,
    )
    schd = scheduler(
        flow(
            {
                'scheduling': {
                    'graph': {'R1': 'a'},
                },
                'runtime': {
                    'a': {'run mode': 'skip'}
                }
            },
        ),
        paused_start=True,
        run_mode=workflow_run_mode,
    )
    async with start(schd):

        [itask] = schd.pool.get_tasks()
        itask.state_reset(
            is_held=attributes_bool,
            is_queued=attributes_bool,
            is_runahead=attributes_bool
        )
        itask.flow_nums = set(flow_nums)

        schd.pool.data_store_mgr.delta_task_held(
            itask.tdef.name, itask.point, itask.state.is_held)
        schd.pool.data_store_mgr.delta_task_state(itask)
        schd.pool.data_store_mgr.delta_task_flow_nums(itask)
        await schd.update_data_structure()

        ret = await show(
            schd.workflow,
            [Tokens('//1/*')],
            opts,
        )
        assert ret == 0

    out, _ = capsys.readouterr()
    assert [
        line for line in out.splitlines()
        if line.startswith("state:")
    ] == [
        expected_state.format(run_mode_info),
    ]

    if expected_flows is not None:
        assert [
            line for line in out.splitlines()
            if line.startswith("flows:")
        ] == [
            expected_flows,
        ]


async def test_task_run_mode_changes(flow, scheduler, start, capsys):
    """Broadcasting a change of run mode changes run mode shown by cylc show.
    """
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        task_defs=None,
        list_prereqs=False,
    )
    schd = scheduler(
        flow({'scheduling': {'graph': {'R1': 'a'}}}),
        run_mode='live'
    )

    async with start(schd):
        # Control: No mode set, the Run Mode setting is not shown:
        await schd.update_data_structure()
        ret = await show(
            schd.workflow,
            [Tokens('//1/a')],
            opts,
        )
        assert ret == 0
        out, _ = capsys.readouterr()
        state, = RE_STATE.findall(out)
        assert 'waiting' in state

        # Broadcast change task to skip mode:
        schd.broadcast_mgr.put_broadcast(['1'], ['a'], [{'run mode': 'skip'}])
        await schd.update_data_structure()

        # show now shows skip mode:
        ret = await show(
            schd.workflow,
            [Tokens('//1/a')],
            opts,
        )
        assert ret == 0

        out, _ = capsys.readouterr()
        state, = RE_STATE.findall(out)
        assert 'run mode=Skip' in state
