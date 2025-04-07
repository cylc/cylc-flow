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

import pytest

from cylc.flow.config import WorkflowConfig
from cylc.flow.taskdef import generate_graph_parents
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.cycling.integer import IntegerPoint


from .test_config import tmp_flow_config   # noqa: F401

param = pytest.param


def test_generate_graph_parents_1(tmp_flow_config):   # noqa: F811
    """Test that parents are only generated from valid recurrences."""
    id_ = 'pan-galactic'
    flow_file = tmp_flow_config(
        id_,
        """
            [scheduler]
                UTC mode = True
            [scheduling]
                initial cycle point = 2023
                [[graph]]
                    R1 = run_once_at_midnight
                    T00 = run_once_at_midnight[-PT0H] => every_cycle
                    T03 = run_once_at_midnight[-PT3H] => every_cycle
                    T06 = run_once_at_midnight[-PT6H] => every_cycle
            [runtime]
                [[every_cycle, run_once_at_midnight]]
        """
    )
    cfg = WorkflowConfig(workflow=id_, fpath=flow_file, options=None)

    # Each instance of every_cycle should have a parent only at T00.
    for point in [
        ISO8601Point('20230101T00'),
        ISO8601Point('20230101T03'),
        ISO8601Point('20230101T06')
    ]:
        parents = generate_graph_parents(
            cfg.taskdefs['every_cycle'], point, cfg.taskdefs
        )
        assert list(parents.values()) == [
            [
                (
                    "run_once_at_midnight",
                    ISO8601Point('20230101T0000Z'),
                    False
                )
            ]
        ]


def test_generate_graph_parents_2(tmp_flow_config):   # noqa: F811
    """Test inferred parents are valid w.r.t to their own recurrences."""
    id_ = 'gargle-blaster'
    flow_file = tmp_flow_config(
        id_,
        """
            [scheduling]
                cycling mode = integer
                [[graph]]
                    P1 = "foo[-P1] => foo"
            [runtime]
                [[foo]]
        """
    )
    cfg = WorkflowConfig(workflow=id_, fpath=flow_file, options=None)

    # Each instance of every_cycle should have a parent only at T00.
    parents = generate_graph_parents(
        cfg.taskdefs['foo'], IntegerPoint("1"), cfg.taskdefs
    )
    assert list(parents.values()) == [[]]  # No parents at first point.

    parents = generate_graph_parents(
        cfg.taskdefs['foo'], IntegerPoint("2"), cfg.taskdefs
    )

    assert list(parents.values()) == [
        [
            (
                "foo",
                IntegerPoint('1'),
                False
            )
        ]
    ]


@pytest.mark.parametrize(
    "task, point, expected",
    [
        param(
            'foo',
            IntegerPoint("1"),
            ['0/foo'],
            id='it.gets-prerequisites',
        ),
        param(
            'multiple_pre',
            IntegerPoint("2"),
            ['2/food', '2/fool', '2/foolhardy', '2/foolish'],
            id='it.gets-multiple-prerequisites',
        ),
        param(
            'foo',
            IntegerPoint("3"),
            [],
            id='it.only-returns-for-valid-points',
        ),
        param(
            'bar',
            IntegerPoint("2"),
            [],
            id='it.does-not-return-suicide-triggers',
        ),
    ],
)
def test_get_prereqs(tmp_flow_config, task, point, expected):  # noqa: F811

    """Test that get_prereqs() returns the correct prerequisites
    for a task."""
    id_ = 'gargle-blaster'
    flow_file = tmp_flow_config(
        id_,
        """
            [scheduler]
                allow implicit tasks = True
            [scheduling]
                final cycle point = 2
                cycling mode = integer
                [[graph]]
                    P1 = '''
                        foo[-P1] => foo
                        bar:fail? => !bar
                        food & fool => multiple_pre
                        foolish | foolhardy => multiple_pre
                    '''
        """
    )
    cfg = WorkflowConfig(workflow=id_, fpath=flow_file, options=None)
    taskdef = cfg.taskdefs[task]
    point = IntegerPoint(point)
    res = sorted([
        condition.get_id()
        for pre in taskdef.get_prereqs(point)
        for condition in pre.keys()
    ])
    assert res == expected
