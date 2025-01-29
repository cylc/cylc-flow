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

"""Tests for the backend method of workflow_state"""

import pytest

from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.scheduler import Scheduler


@pytest.fixture(scope='module')
async def checker(
    mod_flow, mod_scheduler, mod_run, mod_complete
):
    """Make a real world database.

    We could just write the database manually but this is a better
    test of the overall working of the function under test.
    """
    wid = mod_flow({
        'scheduling': {
            'initial cycle point': '1000',
            'final cycle point': '1001',
            'graph': {
                'P1Y': '''
                    good:succeeded
                    bad:failed?
                    output:custom_output
                 '''
            },
        },
        'runtime': {
            'bad': {'simulation': {'fail cycle points': '1000'}},
            'output': {'outputs': {'trigger': 'message', 'custom_output': 'foo'}}
        }
    })
    schd: Scheduler = mod_scheduler(wid, paused_start=False)
    async with mod_run(schd):
        # allow a cycle of the main loop to pass so that flow 2 can be
        # added to db
        await mod_complete(schd)

        # trigger a new task in flow 2
        schd.pool.force_trigger_tasks(['1000/good'], ['2'])

        # update the database
        schd.process_workflow_db_queue()

        # yield a DB checker
        with CylcWorkflowDBChecker(
            'somestring', 'utterbunkum', schd.workflow_db_mgr.pub_path
        ) as _checker:
            yield _checker


def test_basic(checker):
    """Pass no args, get unfiltered output"""
    result = checker.workflow_state_query()
    expect = [
        ['bad', '10000101T0000Z', 'failed'],
        ['bad', '10010101T0000Z', 'succeeded'],
        ['good', '10000101T0000Z', 'succeeded'],
        ['good', '10010101T0000Z', 'succeeded'],
        ['output', '10000101T0000Z', 'succeeded'],
        ['output', '10010101T0000Z', 'succeeded'],
        ['good', '10000101T0000Z', 'waiting', '(flows=2)'],
        ['good', '10010101T0000Z', 'waiting', '(flows=2)'], ]
    assert sorted(result) == sorted(expect)


def test_task(checker):
    """Filter by task name"""
    result = checker.workflow_state_query(task='bad')
    assert sorted(result) == ([
        ['bad', '10000101T0000Z', 'failed'],
        ['bad', '10010101T0000Z', 'succeeded']
    ])


def test_point(checker):
    """Filter by point"""
    result = checker.workflow_state_query(cycle='10000101T0000Z')
    assert sorted(result) == sorted([
        ['bad', '10000101T0000Z', 'failed'],
        ['good', '10000101T0000Z', 'succeeded'],
        ['output', '10000101T0000Z', 'succeeded'],
        ['good', '10000101T0000Z', 'waiting', '(flows=2)'],
    ])


def test_status(checker):
    """Filter by status"""
    result = checker.workflow_state_query(selector='failed')
    expect = [
        ['bad', '10000101T0000Z', 'failed'],
    ]
    assert result == expect


def test_output(checker):
    """Filter by flow number"""
    result = checker.workflow_state_query(selector='message', is_message=True)
    expect = [
        [
            'output',
            '10000101T0000Z',
            "{'submitted': 'submitted', 'started': 'started', 'succeeded': "
            "'succeeded', 'trigger': 'message', 'custom_output': 'foo'}",
        ],
        [
            'output',
            '10010101T0000Z',
            "{'submitted': 'submitted', 'started': 'started', 'succeeded': "
            "'succeeded', 'trigger': 'message', 'custom_output': 'foo'}",
        ],
    ]
    assert result == expect


def test_flownum(checker):
    """Pass no args, get unfiltered output"""
    result = checker.workflow_state_query(flow_num=2)
    expect = [
        ['good', '10000101T0000Z', 'waiting', '(flows=2)'],
        ['good', '10010101T0000Z', 'waiting', '(flows=2)'],
    ]
    assert result == expect
