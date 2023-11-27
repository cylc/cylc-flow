#!/usr/bin/env python3
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

import asyncio
from copy import deepcopy
from pathlib import Path
import re

from async_timeout import timeout

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.id import Tokens
from cylc.flow.tui.updater import (
    Updater,
    get_default_filters,
)
from cylc.flow.workflow_status import WorkflowStatus


async def await_update(updater):
    """Wait for the latest update from the Updater.

    Note:
        If multiple updates are waiting, this returns the most recent.Q

    Returns:
        The latest update from the Updater's "update_queue".

    """
    while updater.update_queue.empty():
        await asyncio.sleep(0.1)
    while not updater.update_queue.empty():
        # flush out any older updates to avoid race conditions in tests
        update = updater.update_queue.get()
    return update


async def wait_workflow_connected(updater, tokens, connected=True, time=3):
    """Wait for the Updater to connect to a workflow.

    This will return once the updater has connected to a workflow and returned
    the first data from it.

    Arugments:
        tokens:
            The tokens of the workflow you're waiting for.
        connected:
            If True this waits for the updater to connect to the workflow, if
            False it waits for the updater to disconnect from it.
        time:
            The maximum time to wait for this to happen.

    Returns:
        The first update from the Updater which contains the workflow data.

    """
    async with timeout(time):
        while True:
            root_node = await await_update(updater)
            workflow_node = root_node['children'][0]
            for workflow_node in root_node['children']:
                if (
                    workflow_node['id_'] == tokens.id
                    and (
                        workflow_node['children'][0]['id_'] != '#spring'
                    ) == connected
                ):
                    # if the spring node is still there then we haven't
                    # recieved the first update from the workflow yet
                    return root_node


def get_child_tokens(root_node, types, relative=False):
    """Return all ID of the specified types contained within the provided tree.

    Args:
        root_node:
            The Tui tree you want to look for IDs in.
        types:
            The Tui types (e.g. 'workflow' or 'task') you want to extract.
        relative:
            If True, the relative IDs will be returned.

    """
    ret = set()
    stack = [root_node]
    while stack:
        node = stack.pop()
        stack.extend(node['children'])
        if node['type_'] in types:

            tokens = Tokens(node['id_'])
            if relative:
                ret.add(tokens.relative_id)
            else:
                ret.add(tokens.id)
    return ret


async def test_subscribe(one_conf, flow, scheduler, run, test_dir):
    """It should subscribe and unsubscribe from workflows."""
    id_ = flow(one_conf)
    schd = scheduler(id_)

    updater = Updater()

    async def the_test():
        nonlocal updater

        try:
            # wait for the first update
            root_node = await await_update(updater)

            # there should be a root root_node
            assert root_node['id_'] == 'root'
            # a single root_node representing the workflow
            assert root_node['children'][0]['id_'] == schd.tokens.id
            # and a "spring" root_node used to active the subscription
            # mechanism
            assert root_node['children'][0]['children'][0]['id_'] == '#spring'

            # subscribe to the workflow
            updater.subscribe(schd.tokens.id)

            # wait for it to connect to the workflow
            root_node = await wait_workflow_connected(updater, schd.tokens)

            # check the workflow contains one cycle with one task in it
            workflow_node = root_node['children'][0]
            assert len(workflow_node['children']) == 1
            cycle_node = workflow_node['children'][0]
            assert Tokens(cycle_node['id_']).relative_id == '1'  # cycle ID
            assert len(cycle_node['children']) == 1
            task_node = cycle_node['children'][0]
            assert Tokens(task_node['id_']).relative_id == '1/one'  # task ID

            # unsubscribe from the workflow
            updater.unsubscribe(schd.tokens.id)

            # wait for it to disconnect from the workflow
            root_node = await wait_workflow_connected(
                updater,
                schd.tokens,
                connected=False,
            )

        finally:
            # shut down the updater
            updater.terminate()

    async with run(schd):
        filters = get_default_filters()
        filters['workflows']['id'] = f'{re.escape(str(test_dir.relative_to(Path("~/cylc-run").expanduser())))}/.*'

        # run the updater and the test
        async with timeout(10):
            await asyncio.gather(
                asyncio.create_task(updater.run(filters)),
                asyncio.create_task(the_test()),
            )


async def test_filters(one_conf, flow, scheduler, run, test_dir):
    """It should filter workflow and task states.

    Note:
        The workflow ID filter is not explicitly tested here, but it is
        indirectly tested, otherwise other workflows would show up in the
        updater results.

    """
    one = scheduler(flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': 'a & b & c',
            }
        }
    }, name='one'), paused_start=True)
    two = scheduler(flow(one_conf, name='two'))
    tre = scheduler(flow(one_conf, name='tre'))

    filters = get_default_filters()
    id_base = str(test_dir.relative_to(Path("~/cylc-run").expanduser()))
    filters['workflows']['id'] = f'^{re.escape(id_base)}/.*'

    updater = Updater()

    async def the_test():
        nonlocal filters
        try:
            root_node = await await_update(updater)
            assert {child['id_'] for child in root_node['children']} == {
                one.tokens.id,
                two.tokens.id,
                tre.tokens.id,
            }

            # filter out paused workflows
            filters = deepcopy(filters)
            filters['workflows'][WorkflowStatus.STOPPED.value] = True
            filters['workflows'][WorkflowStatus.PAUSED.value] = False
            updater.update_filters(filters)

            # "one" and "two" should now be filtered out
            root_node = await await_update(updater)
            assert {child['id_'] for child in root_node['children']} == {
                tre.tokens.id,
            }

            # filter out stopped workflows
            filters = deepcopy(filters)
            filters['workflows'][WorkflowStatus.STOPPED.value] = False
            filters['workflows'][WorkflowStatus.PAUSED.value] = True
            updater.update_filters(filters)

            # "tre" should now be filtered out
            root_node = await await_update(updater)
            assert {child['id_'] for child in root_node['children']} == {
                one.tokens.id,
                two.tokens.id,
            }

            # subscribe to "one"
            updater.subscribe(one.tokens.id)
            root_node = await wait_workflow_connected(updater, one.tokens)
            assert get_child_tokens(
                root_node, types={'task'}, relative=True
            ) == {
                '1/a',
                '1/b',
                '1/c',
            }

            # filter out running tasks
            # TODO: see https://github.com/cylc/cylc-flow/issues/5716
            # filters = deepcopy(filters)
            # filters['tasks'][TASK_STATUS_RUNNING] = False
            # updater.update_filters(filters)

            # root_node = await await_update(updater)
            # assert get_child_tokens(
            #   root_node,
            #   types={'task'},
            #   relative=True
            # ) == {
            #     '1/b',
            #     '1/c',
            # }

        finally:
            # shut down the updater
            updater.terminate()

    # start workflow "one"
    async with run(one):
        # mark "1/a" as running and "1/b" as succeeded
        one_a = one.pool.get_task(IntegerPoint('1'), 'a')
        one_a.state_reset('running')
        one.data_store_mgr.delta_task_state(one_a)
        one.pool.get_task(IntegerPoint('1'), 'b').state_reset('succeeded')

        # start workflow "two"
        async with run(two):
            # run the updater and the test
            async with timeout(10):
                await asyncio.gather(
                    asyncio.create_task(the_test()),
                    asyncio.create_task(updater.run(filters)),
                )
