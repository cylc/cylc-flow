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

from cylc.flow.config import WorkflowConfig
from cylc.flow.taskdef import generate_graph_parents
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.cycling.integer import IntegerPoint

from .test_config import tmp_flow_config


def test_generate_graph_parents_1(tmp_flow_config):
    """Test that parents are only generated from valid recurrences."""
    reg = 'pan-galactic'
    flow_file = tmp_flow_config(
        reg,
        f"""
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
    cfg = WorkflowConfig(workflow=reg, fpath=flow_file, options=None)

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


def test_generate_graph_parents_2(tmp_flow_config):
    """Test inferred parents are valid w.r.t to their own recurrences."""
    reg = 'gargle-blaster'
    flow_file = tmp_flow_config(
        reg,
        f"""
            [scheduling]
                cycling mode = integer
                [[graph]]
                    P1 = "foo[-P1] => foo"
            [runtime]
                [[foo]]
        """
    )
    cfg = WorkflowConfig(workflow=reg, fpath=flow_file, options=None)

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
