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


from datetime import (
    datetime,
    timedelta
)
from unittest.mock import Mock

import pytest

from cylc.flow.tui.util import (
    JOB_ICON,
    TASK_ICONS,
    render_node,
    compute_tree,
    get_task_icon
)
from cylc.flow.wallclock import (
    get_time_string,
    get_current_time_string
)


def testrender_node__job_info():
    """It renders job information nodes."""
    assert render_node(
        None,
        {'a': 1, 'b': 2},
        'job_info'
    ) == [
        'a  1\n',
        'b  2'
    ]


def testrender_node__job():
    """It renders job nodes."""
    assert render_node(
        None,
        {'state': 'succeeded', 'submitNum': 1},
        'job'
    ) == [
        '#01 ',
        [('job_succeeded', JOB_ICON)]
    ]


def testrender_node__task__succeeded():
    """It renders tasks."""
    node = Mock()
    node.get_child_node = lambda _: None
    assert render_node(
        node,
        {
            'name': 'foo',
            'state': 'succeeded',
            'isHeld': False,
            'isQueued': False,
            'isRunahead': False
        },
        'task'
    ) == [
        TASK_ICONS['succeeded'],
        ' ',
        'foo'
    ]


def testrender_node__task__running():
    """It renders running tasks."""
    child = Mock()
    child.get_value = lambda: {'data': {
        'startedTime': get_current_time_string(),
        'state': 'running'
    }}
    node = Mock()
    node.get_child_node = lambda _: child
    assert render_node(
        node,
        {
            'name': 'foo',
            'state': 'running',
            'isHeld': False,
            'isQueued': False,
            'isRunahead': False,
            'task': {'meanElapsedTime': 100}
        },
        'task'
    ) == [
        TASK_ICONS['running'],
        ' ',
        ('job_running', JOB_ICON),
        ' ',
        'foo'
    ]


def testrender_node__family():
    """It renders families."""
    assert render_node(
        None,
        {
            'state': 'succeeded',
            'isHeld': False,
            'isQueued': False,
            'isRunahead': False,
            'id': 'myid'
        },
        'family'
    ) == [
        [TASK_ICONS['succeeded']],
        ' ',
        'myid'
    ]


def testrender_node__cycle_point():
    """It renders cycle points."""
    assert render_node(
        None,
        {'id': 'myid'},
        'cycle_point'
    ) == 'myid'


@pytest.mark.parametrize(
    'status,is_held,is_queued,is_runahead,start_offset,mean_time,expected',
    [
        # task states
        ('waiting', False, False, False, None, None, ['○']),
        ('submitted', False, False, False, None, None, ['⊙']),
        ('running', False, False, False, None, None, ['⊙']),
        ('succeeded', False, False, False, None, None, ['●']),
        ('submit-failed', False, False, False, None, None, ['⊘']),
        ('failed', False, False, False, None, None, ['⊗']),
        # progress indicator
        ('running', False, False, False, 0, 100, ['⊙']),
        ('running', False, False, False, 25, 100, ['◔']),
        ('running', False, False, False, 50, 100, ['◑']),
        ('running', False, False, False, 75, 100, ['◕']),
        ('running', False, False, False, 100, 100, ['◕']),
        # is-held modifier
        ('waiting', True, False, False, None, None, ['\u030E', '○']),
        # is-queued modifier
        ('waiting', False, True, False, None, None, ['\u033F', '○']),
        # is-runahead modifier
        ('waiting', False, False, True, None, None, ['\u030A', '○'])
    ]
)
def test_get_task_icon(
        status, is_held, is_queued, is_runahead, start_offset, mean_time,
        expected):
    """It renders task icons."""
    start_time = None
    if start_offset is not None:
        start_time = get_time_string(
            datetime.utcnow() - timedelta(seconds=start_offset)
        )
    assert (
        get_task_icon(
            status, is_held=is_held, is_queued=is_queued,
            is_runahead=is_runahead, start_time=start_time,
            mean_time=mean_time
        )
    ) == expected


def test_compute_tree():
    """It computes a tree in the right structure for urwid.

    Note this test doesn't use full data or propper ids because it's
    purpose is not to test the GraphQL interface but to ensure the
    assumptions made by compute_tree check out.

    """
    tree = compute_tree({
        'workflows': [{
            'id': 'workflow id',
            'port': 1234,
            'cyclePoints': [
                {
                    'id': '1/family-suffix',
                    'cyclePoint': '1'
                }
            ],
            'familyProxies': [
                {  # top level family
                    'name': 'FOO',
                    'id': '1/FOO',
                    'cyclePoint': '1',
                    'firstParent': {'name': 'root', 'id': '1/root'}
                },
                {  # nested family
                    'name': 'FOOT',
                    'id': '1/FOOT',
                    'cyclePoint': '1',
                    'firstParent': {'name': 'FOO', 'id': '1/FOO'}
                },
            ],
            'taskProxies': [
                {  # top level task
                    'name': 'pub',
                    'id': '1/pub',
                    'firstParent': {'name': 'root', 'id': '1/root'},
                    'cyclePoint': '1',
                    'jobs': []
                },
                {  # child task (belongs to family)
                    'name': 'fan',
                    'id': '1/fan',
                    'firstParent': {'name': 'fan', 'id': '1/fan'},
                    'cyclePoint': '1',
                    'jobs': []
                },
                {  # nested child task (belongs to incestuous family)
                    'name': 'fool',
                    'id': '1/fool',
                    'firstParent': {'name': 'FOOT', 'id': '1/FOOT'},
                    'cyclePoint': '1',
                    'jobs': []
                },
                {  # a task which has jobs
                    'name': 'worker',
                    'id': '1/worker',
                    'firstParent': {'name': 'root', 'id': '1/root'},
                    'cyclePoint': '1',
                    'jobs': [
                        {'id': '1/worker/03', 'submitNum': '3'},
                        {'id': '1/worker/02', 'submitNum': '2'},
                        {'id': '1/worker/01', 'submitNum': '1'}
                    ]
                }
            ]
        }]
    })

    # the root node
    assert tree['type_'] == 'root'
    assert tree['id_'] == 'root'
    assert len(tree['children']) == 1

    # the workflow node
    workflow = tree['children'][0]
    assert workflow['type_'] == 'workflow'
    assert workflow['id_'] == 'workflow id'
    assert set(workflow['data']) == {
        # whatever if present on the node should end up in data
        'cyclePoints',
        'familyProxies',
        'id',
        'port',
        'taskProxies'
    }
    assert len(workflow['children']) == 1

    # the cycle point node
    cycle = workflow['children'][0]
    assert cycle['type_'] == 'cycle'
    assert cycle['id_'] == '//1'
    assert list(cycle['data']) == [
        'id',
        'cyclePoint'
    ]
    assert len(cycle['children']) == 3
    assert [
        node['id_']
        for node in cycle['children']
    ] == [
        # test alphabetical sorting
        '1/FOO',
        '1/pub',
        '1/worker'
    ]

    # test family node
    family = cycle['children'][0]
    assert family['type_'] == 'family'
    assert family['id_'] == '1/FOO'
    assert list(family['data']) == [
        'name',
        'id',
        'cyclePoint',
        'firstParent'
    ]
    assert len(family['children']) == 1

    # test nested family
    nested_family = family['children'][0]
    assert nested_family['type_'] == 'family'
    assert nested_family['id_'] == '1/FOOT'
    assert list(nested_family['data']) == [
        'name',
        'id',
        'cyclePoint',
        'firstParent'
    ]
    assert len(nested_family['children']) == 1

    # test task
    task = nested_family['children'][0]
    assert task['type_'] == 'task'
    assert task['id_'] == '1/fool'
    assert list(task['data']) == [
        'name',
        'id',
        'firstParent',
        'cyclePoint',
        'jobs'
    ]
    assert len(task['children']) == 0

    # test task with jobs
    task = cycle['children'][-1]
    assert [  # test sorting
        job['id_']
        for job in task['children']
    ] == [
        '1/worker/03',
        '1/worker/02',
        '1/worker/01'
    ]

    # test job
    job = task['children'][0]
    assert job['type_'] == 'job'
    assert job['id_'] == '1/worker/03'
    assert list(job['data']) == [
        'id',
        'submitNum'
    ]
    assert len(job['children']) == 1

    # test job info
    job_info = job['children'][0]
    assert job_info['type_'] == 'job_info'
    assert job_info['id_'] == '1/worker/03_info'
    assert list(job_info['data']) == [
        'id',
        'submitNum'
    ]
    assert len(job_info['children']) == 0
