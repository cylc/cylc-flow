# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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

import sqlite3

from metomi.isodatetime.data import TimePoint
import pytest

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker, check_polling_config
from cylc.flow.exceptions import InputError


def test_check_polling_config():
    """It should reject invalid or unreliable polling configurations.

    See https://github.com/cylc/cylc-flow/issues/6157
    """
    # invalid polling use cases
    with pytest.raises(InputError, match='No such task state'):
        check_polling_config('elephant', False, False)

    with pytest.raises(InputError, match='Cannot poll for'):
        check_polling_config('waiting', False, False)

    with pytest.raises(InputError, match='is not reliable'):
        check_polling_config('running', False, False)

    # valid polling use cases
    check_polling_config('started', True, False)
    check_polling_config('started', False, True)

    # valid query use cases
    check_polling_config(None, False, True)
    check_polling_config(None, False, False)


class MockConn(sqlite3.Connection):
    """Mock Connection that allows asserting inputs and providing outputs."""
    def __init__(self, rows: list[tuple], expected_statement: str | None = None, expected_parameters: tuple | None = None) -> None:
        self.rows = rows
        self.expected_stmt = expected_statement
        self.expected_parameters = expected_parameters

    def execute(self, sql: str, parameters = None): # type: ignore
        if self.expected_stmt is not None:
            assert self.expected_stmt == sql
        assert self.expected_parameters == parameters
        return self

    def fetchone(self):
        return self.rows[0] if len(self.rows) > 0 else None

    def fetchall(self):
        return self.rows

class MockDBChecker(CylcWorkflowDBChecker):
    """Mock CylcWorkflowDBChecker that doesn't need a real database."""
    def __init__(self, conn: MockConn | None, db_point_fmt: str | None=None):
        self.conn = conn if conn is not None else MockConn([])
        self.db_point_fmt = db_point_fmt


class TestCylcWorkflowDBChecker:
    int_point = IntegerPoint("5")
    time_point = TimePoint(year=2026, month_of_year=9, day_of_month=25)

    @pytest.mark.parametrize(
            "expected, cycle_string, db_point_fmt",
            [
                # IntegerPoint produced.
                (int_point, "5", None),
                # TimePoint produced.
                (time_point, "20260925T0000Z", "CCYYMMDDThhmmZ"),
            ]
    )
    def test_str_to_point(self, expected, cycle_string, db_point_fmt):
        """String produces expected Point object."""
        point = MockDBChecker(None, db_point_fmt)._str_to_point(cycle_string)
        assert point == expected

    def test_str_to_point_invalid_format(self):
        """An improperly formatted cycle point raises an error."""
        with pytest.raises(
            InputError,
            match='Cycle point "not a date" is not compatible with DB point format "CCYYMMDDThhmmZ"',
        ):
            MockDBChecker(None, "CCYYMMDDThhmmZ")._str_to_point("not a date")

    @pytest.mark.parametrize(
            "expected, cycle, offset, db_point_fmt",
            [
                # None cycles are returned unchanged.
                (None, None, None, None),
                # Integer cycles without offsets are returned unchanged.
                ("1", "1", None, None),
                # Offsets are applied to integer offsets.
                ("1", "2", "-P1", None),
                ("3", "2", "P1", None),
                # Date cycles are normalised.
                ("20260925T0000Z", "2026-09-25T00:00Z", None, "CCYYMMDDThhmmZ"),
                # Date cycles have offsets applied.
                ("20260924T0000Z", "20260925T0000Z", "-P1D", "CCYYMMDDThhmmZ"),
                ("20260926T0000Z", "20260925T0000Z", "+P1D", "CCYYMMDDThhmmZ"),
            ]
    )
    def test_adjust_point_to_db(self, expected, cycle, offset, db_point_fmt):
        """Cycle point is offset and normalised."""
        db_checker = MockDBChecker(None, db_point_fmt)
        normalised_cycle = db_checker.adjust_point_to_db(cycle, offset)
        assert normalised_cycle == expected

    @pytest.mark.parametrize(
            "expected,rows,db_point_fmt",
            [
                # No start cycle point if not in database.
                (None, [], None),
                # No start cycle point if blank in database.
                (None, [("",)], None),
                # IntegerPoint created when db_point_fmt is None.
                (IntegerPoint("1"), [("1",)], None),
                (IntegerPoint("42"), [("42",)], None),
                # TimePoint created when db_point_fmt is set.
                (time_point, [("20260925T0000Z",)], "CCYYMMDDThhmmZ"),
            ]
    )
    def test_get_start_cycle_point(self, expected, rows, db_point_fmt):
        """The start cycle point is converted into an appropriate Point object."""
        db_checker = MockDBChecker(MockConn(rows), db_point_fmt)
        start_cycle_point = db_checker._get_start_cycle_point()
        assert start_cycle_point == expected

    @pytest.mark.parametrize(
            "expected, db_point_fmt, start_cycle_point,target_cycle_point",
            [
                # Not before an unspecified start cycle point.
                (False, None, None, "1"),
                # Non-specific target cycle point is not before.
                (False, None, int_point, "*"),
                (False, None, int_point, "%"),
                (False, "CCYYMMDDThhmmZ", time_point, "*"),
                (False, "CCYYMMDDThhmmZ", time_point, "%"),
                # Target is equal or after start cycle point.
                (False, None, int_point, "5"),
                (False, None, int_point, "6"),
                # Target is before start cycle point.
                (True, None, int_point, "2"),
                # TimePoint is equal or after start cycle point.
                (False, "CCYYMMDDThhmmZ", time_point, "20260925T0000Z"),
                (False, "CCYYMMDDThhmmZ", time_point, "20260930T0000Z"),
                # TimePoint is before start cycle point.
                (True, "CCYYMMDDThhmmZ", time_point, "20260901T0000Z"),
            ]
    )
    def test_is_before_start_cycle_point(
        self, expected, db_point_fmt, start_cycle_point, target_cycle_point
    ):
        """Whether the current cycle point is before the start cycle point."""
        db_checker = MockDBChecker(None, db_point_fmt)
        db_checker.start_cycle_point = start_cycle_point
        before_start_cycle_point = db_checker._is_before_start_cycle_point(
            target_cycle_point
        )
        assert before_start_cycle_point == expected

    @pytest.mark.parametrize(
            "expected, task, cycle, selector, flow_num, is_output_query",
            [
                # Test defaults.
                (["", "1", "succeeded"], None, "1", None, None, None),
                # Test task name, alternative succeeded, and cycle.
                (["mytask", "2", "succeeded"], "mytask", "2", "succeeded", None, False),
                # Test date cycle and flow number.
                (["mytask", "20260926T1200Z", "succeeded", "3"], "mytask", "20260926T1200Z", "succeeded", 3, False),
                # Test an output query.
                (["mytask", "1", '{"custom": "before start cycle point"}'], "mytask", "1", "custom", None, True),
            ]
    )
    def test_dummy_result(
        self, expected, task, cycle, selector, flow_num, is_output_query
    ):
        """It should produce the expected result."""
        assert (
            CylcWorkflowDBChecker._dummy_result(
                task, cycle, selector, flow_num, is_output_query
            )
            == expected
        )
