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
    get_group_state,
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
            'isHeld': False
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
        {'state': 'succeeded', 'isHeld': False, 'id': 'myid'},
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
    'status,is_held,start_offset,mean_time,expected',
    [
        # task states
        ('waiting', False, None, None, ['○']),
        ('submitted', False, None, None, ['⊙']),
        ('running', False, None, None, ['⊙']),
        ('succeeded', False, None, None, ['●']),
        ('submit-failed', False, None, None, ['⊗']),
        ('failed', False, None, None, ['⊗']),
        # progress indicator
        ('running', False, 0, 100, ['⊙']),
        ('running', False, 25, 100, ['◔']),
        ('running', False, 50, 100, ['◑']),
        ('running', False, 75, 100, ['◕']),
        ('running', False, 100, 100, ['◕']),
        # is-held modifier
        ('waiting', True, None, None, ['\u030E', '○'])
    ]
)
def test_get_task_icon(status, is_held, start_offset, mean_time, expected):
    """It renders task icons."""
    start_time = None
    if start_offset is not None:
        start_time = get_time_string(
            datetime.utcnow() - timedelta(seconds=start_offset)
        )
    assert (
        get_task_icon(status, is_held, start_time, mean_time)
    ) == expected


@pytest.mark.parametrize(
    'nodes,expected',
    [
        (
            [
                ('waiting', False),
                ('running', False)
            ],
            ('running', False)
        ),
        (
            [
                ('waiting', False),
                ('running', True)
            ],
            ('running', True)
        )
    ]
)
def test_get_group_state(nodes, expected):

    def make_node(data):
        node = Mock()
        node.get_value = lambda: {'data': data}
        return node

    nodes = [
        make_node(
            {'state': state, 'isHeld': is_held}
        )
        for state, is_held in nodes
    ]
    assert get_group_state(nodes) == expected


def test_compute_tree():
    """It computes a tree in the right structure for urwid.

    This is a pretty rough and ready test, describe cases to trigger all
    branches in the method then record the result.

    """
    assert compute_tree({
        'id': 'workflow id',
        'familyProxies': [
            {  # root family node
                'name': 'root',
                'id': 'root.1',
                'cyclePoint': '1',
                'firstParent': None
            },
            {  # top level family
                'name': 'FOO',
                'id': 'FOO.1',
                'cyclePoint': '1',
                'firstParent': {'name': 'root', 'id': 'root.1'}
            },
            {  # nested family
                'name': 'FOOT',
                'id': 'FOOT.1',
                'cyclePoint': '1',
                'firstParent': {'name': 'FOO', 'id': 'FOO.1'}
            },
        ],
        'taskProxies': [
            {  # orphan task (belongs to no family)
                'name': 'baz',
                'id': 'baz.1',
                'parents': [],
                'cyclePoint': '1',
                'jobs': []
            },
            {  # top level task
                'name': 'pub',
                'id': 'pub.1',
                'parents': [{'name': 'root', 'id': 'root.1'}],
                'cyclePoint': '1',
                'jobs': []
            },
            {  # child task (belongs to family)
                'name': 'fan',
                'id': 'fan.1',
                'parents': [{'name': 'fan', 'id': 'fan.1'}],
                'cyclePoint': '1',
                'jobs': []
            },
            {  # nested child task (belongs to incestuous family)
                'name': 'fool',
                'id': 'fool.1',
                'parents': [
                    {'name': 'FOO', 'id': 'FOO.1'},
                    {'name': 'FOOT', 'id': 'FOOT.1'}
                ],
                'cyclePoint': '1',
                'jobs': []
            },
            {  # a task which has jobs
                'name': 'worker',
                'id': 'worker.1',
                'parents': [],
                'cyclePoint': '1',
                'jobs': [
                    {'id': 'job1', 'submitNum': '1'},
                    {'id': 'job2', 'submitNum': '2'},
                    {'id': 'job3', 'submitNum': '3'}
                ]
            }
        ]
    }) == {
        "children": [
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [
                                    {
                                        "children": [],
                                        "id_": "job3_info",
                                        "data": {
                                            "id": "job3",
                                            "submitNum": "3"
                                        },
                                        "type_": "job_info"
                                    }
                                ],
                                "id_": "job3",
                                "data": {
                                    "id": "job3",
                                    "submitNum": "3"
                                },
                                "type_": "job"
                            },
                            {
                                "children": [
                                    {
                                        "children": [],
                                        "id_": "job2_info",
                                        "data": {
                                            "id": "job2",
                                            "submitNum": "2"
                                        },
                                        "type_": "job_info"
                                    }
                                ],
                                "id_": "job2",
                                "data": {
                                    "id": "job2",
                                    "submitNum": "2"
                                },
                                "type_": "job"
                            },
                            {
                                "children": [
                                    {
                                        "children": [],
                                        "id_": "job1_info",
                                        "data": {
                                            "id": "job1",
                                            "submitNum": "1"
                                        },
                                        "type_": "job_info"
                                    }
                                ],
                                "id_": "job1",
                                "data": {
                                    "id": "job1",
                                    "submitNum": "1"
                                },
                                "type_": "job"
                            }
                        ],
                        "id_": "worker.1",
                        "data": {
                            "name": "worker",
                            "id": "worker.1",
                            "parents": [],
                            "cyclePoint": "1",
                            "jobs": [
                                {
                                    "id": "job1",
                                    "submitNum": "1"
                                },
                                {
                                    "id": "job2",
                                    "submitNum": "2"
                                },
                                {
                                    "id": "job3",
                                    "submitNum": "3"
                                }
                            ]
                        },
                        "type_": "task"
                    },
                    {
                        "children": [],
                        "id_": "pub.1",
                        "data": {
                            "name": "pub",
                            "id": "pub.1",
                            "parents": [
                                {
                                    "name": "root",
                                    "id": "root.1"
                                }
                            ],
                            "cyclePoint": "1",
                            "jobs": []
                        },
                        "type_": "task"
                    },
                    {
                        "children": [],
                        "id_": "baz.1",
                        "data": {
                            "name": "baz",
                            "id": "baz.1",
                            "parents": [],
                            "cyclePoint": "1",
                            "jobs": []
                        },
                        "type_": "task"
                    },
                    {
                        "children": [
                            {
                                "children": [],
                                "id_": "fool.1",
                                "data": {
                                    "name": "fool",
                                    "id": "fool.1",
                                    "parents": [
                                        {
                                            "name": "FOO",
                                            "id": "FOO.1"
                                        },
                                        {
                                            "name": "FOOT",
                                            "id": "FOOT.1"
                                        }
                                    ],
                                    "cyclePoint": "1",
                                    "jobs": []
                                },
                                "type_": "task"
                            },
                            {
                                "children": [],
                                "id_": "FOOT.1",
                                "data": {
                                    "name": "FOOT",
                                    "id": "FOOT.1",
                                    "cyclePoint": "1",
                                    "firstParent": {
                                        "name": "FOO",
                                        "id": "FOO.1"
                                    }
                                },
                                "type_": "family"
                            }
                        ],
                        "id_": "FOO.1",
                        "data": {
                            "name": "FOO",
                            "id": "FOO.1",
                            "cyclePoint": "1",
                            "firstParent": {
                                "name": "root",
                                "id": "root.1"
                            }
                        },
                        "type_": "family"
                    }
                ],
                "id_": "1",
                "data": {
                    "name": "1",
                    "id": "workflow id|1"
                },
                "type_": "cycle"
            }
        ],
        "id_": "workflow id",
        "data": {
            "id": "workflow id",
            "familyProxies": [
                {
                    "name": "root",
                    "id": "root.1",
                    "cyclePoint": "1",
                    "firstParent": None
                },
                {
                    "name": "FOO",
                    "id": "FOO.1",
                    "cyclePoint": "1",
                    "firstParent": {
                        "name": "root",
                        "id": "root.1"
                    }
                },
                {
                    "name": "FOOT",
                    "id": "FOOT.1",
                    "cyclePoint": "1",
                    "firstParent": {
                        "name": "FOO",
                        "id": "FOO.1"
                    }
                }
            ],
            "taskProxies": [
                {
                    "name": "baz",
                    "id": "baz.1",
                    "parents": [],
                    "cyclePoint": "1",
                    "jobs": []
                },
                {
                    "name": "pub",
                    "id": "pub.1",
                    "parents": [
                        {
                            "name": "root",
                            "id": "root.1"
                        }
                    ],
                    "cyclePoint": "1",
                    "jobs": []
                },
                {
                    "name": "fan",
                    "id": "fan.1",
                    "parents": [
                        {
                            "name": "fan",
                            "id": "fan.1"
                        }
                    ],
                    "cyclePoint": "1",
                    "jobs": []
                },
                {
                    "name": "fool",
                    "id": "fool.1",
                    "parents": [
                        {
                            "name": "FOO",
                            "id": "FOO.1"
                        },
                        {
                            "name": "FOOT",
                            "id": "FOOT.1"
                        }
                    ],
                    "cyclePoint": "1",
                    "jobs": []
                },
                {
                    "name": "worker",
                    "id": "worker.1",
                    "parents": [],
                    "cyclePoint": "1",
                    "jobs": [
                        {
                            "id": "job1",
                            "submitNum": "1"
                        },
                        {
                            "id": "job2",
                            "submitNum": "2"
                        },
                        {
                            "id": "job3",
                            "submitNum": "3"
                        }
                    ]
                }
            ]
        },
        "type_": "workflow"
    }
