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

"""Test Cylc recurring date/time syntax parsing."""

import pytest

from unittest.mock import Mock
from metomi.isodatetime.data import Duration
from cylc.flow.exceptions import CylcTimeSyntaxError
from cylc.flow.time_parser import (
    CylcTimeParser,
    UTC_UTC_OFFSET_HOURS_MINUTES,
)


@pytest.fixture
def parsers():
    _start_point = "19991226T0930Z"
    # Note: the following timezone will be Z-ified *after* truncation
    # or offsets are applied.
    _end_point = "20010506T1200+0200"
    return {
        0: CylcTimeParser(
            _start_point, _end_point,
            CylcTimeParser.initiate_parsers(
                assumed_time_zone=UTC_UTC_OFFSET_HOURS_MINUTES
            )
        ),
        2: CylcTimeParser(
            _start_point, _end_point,
            CylcTimeParser.initiate_parsers(
                num_expanded_year_digits=2,
                assumed_time_zone=UTC_UTC_OFFSET_HOURS_MINUTES
            )
        )
    }


@pytest.mark.parametrize(
    'expression, num_expanded_year_digits, ctrl_data, ctrl_results',
    [
        (
            "R5/T06/04T1230-0300",
            0,
            "R5/19991227T0600Z/20010604T1530Z",
            ["19991227T0600Z", "20010604T1530Z",
             "20021112T0100Z", "20040420T1030Z",
             "20050927T2000Z"]
        ),
        (
            "R2/-0450000101T04Z/+0020630405T2200-05",
            2,
            "R2/-0450000101T0400Z/+0020630406T0300Z",
            ["-0450000101T0400Z", "+0020630406T0300Z"]
        ),
        (
            "R10/T12+P10D/-P1Y",
            0,
            "R10/20000105T1200Z/20000506T1000Z",
            ["20000105T1200Z", "20000506T1000Z",
             "20000905T0800Z", "20010105T0600Z",
             "20010507T0400Z", "20010906T0200Z",
             "20020106T0000Z", "20020507T2200Z",
             "20020906T2000Z", "20030106T1800Z"]
        )
    ]
)
def test_first_recurrence_format(
    expression, num_expanded_year_digits, ctrl_data, ctrl_results,
    parsers
):
    """Test the first ISO 8601 recurrence format."""
    parser = parsers[num_expanded_year_digits]
    recurrence = parser.parse_recurrence(expression)[0]
    test_data = str(recurrence)
    assert test_data == ctrl_data
    test_results = [str(res) for res in recurrence]
    assert test_results == ctrl_results


def test_third_recurrence_format(parsers):
    """Test the third ISO 8601 recurrence format."""
    tests = [("T06", "R/19991227T0600Z/P1D"),
             ("T1230", "R/19991226T1230Z/P1D"),
             ("04T00", "R/20000104T0000Z/P1M"),
             ("01T06/PT2H", "R/20000101T0600Z/PT2H"),
             ("0501T/P4Y3M", "R/20000501T0000Z/P4Y3M"),
             ("P1YT5H", "R/19991226T0930Z/P1YT5H",
                 ["19991226T0930Z", "20001226T1430Z"]),
             ("PT5M", "R/19991226T0930Z/PT5M"),
             ("R/T-40", "R/19991226T0940Z/PT1H"),
             ("R/150401T", "R/20150401T0000Z/P100Y"),
             ("R5/T04-0300", "R5/19991227T0700Z/P1D"),
             ("R2/T23Z/", "R2/19991226T2300Z/P1D"),
             ("R/19991226T2359Z/P1W", "R/19991226T2359Z/P1W"),
             ("R/-P1W/P1W", "R/19991219T0930Z/P1W"),
             ("R/+P1D/P1Y", "R/19991227T0930Z/P1Y"),
             ("R/T06-P1D/PT1H", "R/19991226T0600Z/PT1H"),
             ("R/T12/PT10,5H", "R/19991226T1200Z/PT10,5H"),
             ("R/T12/PT10.5H", "R/19991226T1200Z/PT10,5H"),
             ("R5/+P10Y5M4D/PT2H", "R5/20100529T0930Z/PT2H"),
             ("R30/-P200D/P10D", "R30/19990609T0930Z/P10D"),
             ("R10/T06/PT2H", "R10/19991227T0600Z/PT2H",
                 ["19991227T0600Z", "19991227T0800Z", "19991227T1000Z",
                  "19991227T1200Z", "19991227T1400Z", "19991227T1600Z",
                  "19991227T1800Z", "19991227T2000Z", "19991227T2200Z",
                  "19991228T0000Z"]),
             ("R//P1Y", "R/19991226T0930Z/P1Y",
                 ["19991226T0930Z", "20001226T0930Z"]),
             ("R5//P1D", "R5/19991226T0930Z/P1D",
                 ["19991226T0930Z", "19991227T0930Z",
                  "19991228T0930Z", "19991229T0930Z",
                  "19991230T0930Z"]),
             ("R1", "R1/19991226T0930Z/P0Y",
                 ["19991226T0930Z"])]
    for test in tests:
        if len(test) == 2:
            expression, ctrl_data = test
            ctrl_results = None
        else:
            expression, ctrl_data, ctrl_results = test
        recurrence = (parsers[0].parse_recurrence(expression))[0]
        test_data = str(recurrence)
        assert test_data == ctrl_data
        if ctrl_results is None:
            continue
        test_results = []
        for i, test_result in enumerate(recurrence):
            if i > len(ctrl_results) - 1:
                break
            assert str(test_result) == ctrl_results[i]
            test_results.append(str(test_result))
        assert test_results == ctrl_results


def test_fourth_recurrence_format(parsers):
    """Test the fourth ISO 8601 recurrence format."""
    tests = [("PT6H/20000101T0500Z", "R25/19991226T0500Z/PT6H"),
             ("P12D/+P2W", "R44/19991221T1000Z/P12D"),
             ("R2/P1W/-P1M1D", "R2/P1W/20010405T1000Z"),
             ("R3/P6D/T12+02", "R3/P6D/20010506T1000Z"),
             ("R4/P6DT12H/01T00+02", "R4/P6DT12H/20010531T2200Z"),
             ("R5/P1D/20010506T1200+0200", "R5/P1D/20010506T1000Z"),
             ("R6/PT5M/+PT2M", "R6/PT5M/20010506T1002Z"),
             ("R7/P20Y/-P20Y", "R7/P20Y/19810506T1000Z"),
             ("R8/P3YT2H/T18-02", "R8/P3YT2H/20010506T2000Z"),
             ("R9/PT3H/31T", "R9/PT3H/20010531T0000Z"),
             ("R10/P1Y/", "R10/P1Y/20010506T1000Z"),
             ("R3/P2Y/02T", "R3/P2Y/20010602T0000Z"),
             ("R/P2Y", "R2/19990506T1000Z/P2Y"),
             ("R48/PT2H", "R48/PT2H/20010506T1000Z"),
             ("R100/P21Y/", "R100/P21Y/20010506T1000Z")]
    for test in tests:
        if len(test) == 2:
            expression, ctrl_data = test
            ctrl_results = None
        else:
            expression, ctrl_data, ctrl_results = test
        recurrence = (parsers[0].parse_recurrence(
            expression))[0]
        test_data = str(recurrence)
        assert test_data == ctrl_data
        if ctrl_results is None:
            continue
        test_results = []
        for i, test_result in enumerate(recurrence):
            assert str(test_result) == ctrl_results[i]
            test_results.append(str(test_result))
        assert test_results == ctrl_results


def test_inter_cycle_timepoints(parsers):
    """Test the inter-cycle point parsing."""
    task_cycle_time = parsers[0].parse_timepoint("20000101T00Z")
    tests = [("T06", "20000101T0600Z", 0),
             ("-PT6H", "19991231T1800Z", 0),
             ("+P5Y2M", "20050301T0000Z", 0),
             ("0229T", "20000229T0000Z", 0),
             ("+P54D", "20000224T0000Z", 0),
             ("T12+P5W", "20000205T1200Z", 0),
             ("-P1Y", "19990101T0000Z", 0),
             ("-9999990101T00Z", "-9999990101T0000Z", 2),
             ("20050601T2359+0200", "20050601T2159Z", 0)]
    for expression, ctrl_data, num_expanded_year_digits in tests:
        parser = parsers[num_expanded_year_digits]
        test_data = str(parser.parse_timepoint(
            expression,
            context_point=task_cycle_time))
        assert test_data == ctrl_data


def test_interval(parsers):
    """Test the interval timepoint parsing (purposefully weak tests)."""
    tests = ["PT6H2M", "PT6H", "P2Y5D",
             "P5W", "PT12M2S", "PT65S",
             "PT2M", "P1YT567,4M"]
    for expression in tests:
        test_data = str(parsers[0].parse_interval(expression))
        assert test_data == expression


def test_parse_timepoint_invalid(parsers):
    """It should raise CylcTimeSyntaxError for invalid expressions."""
    with pytest.raises(CylcTimeSyntaxError, match="not a valid"):
        parsers[0].parse_timepoint("not_a_date")


def test_parse_timepoint_none(parsers):
    """It should raise CylcTimeSyntaxError when expr is None."""
    with pytest.raises(CylcTimeSyntaxError, match="not a valid"):
        parsers[0].parse_timepoint(None)


def test_parse_recurrence_invalid(parsers):
    """It should raise CylcTimeSyntaxError for unparsable expressions."""
    with pytest.raises(CylcTimeSyntaxError, match="Could not parse"):
        parsers[0].parse_recurrence("///")


def test_parse_recurrence_with_context(parsers):
    """It should use explicit context points when provided."""
    parser = parsers[0]
    start = parser.parse_timepoint("20000101T00Z")
    end = parser.parse_timepoint("20010101T00Z")
    recurrence = parser.parse_recurrence(
        "R2/P1Y/",
        context_start_point=start,
        context_end_point=end,
    )[0]
    assert str(recurrence) == "R2/P1Y/20010101T0000Z"


def test_get_interval_from_expression(parsers):
    """It should infer interval from truncated context point."""
    parser = parsers[0]

    # when expr is provided, it should just parse it
    assert str(parser._get_interval_from_expression("P1D")) == "P1D"

    # when expr is None and context is None, return None
    assert parser._get_interval_from_expression(None, None) is None

    # when expr is None and context is not truncated, return None
    context = Mock(truncated=False)
    assert parser._get_interval_from_expression(None, context) is None

    # test each truncated property name
    cases = [
        ("year_of_century", Duration(years=100)),
        ("year_of_decade", Duration(years=10)),
        ("month_of_year", Duration(years=1)),
        ("week_of_year", Duration(years=1)),
        ("day_of_year", Duration(years=1)),
        ("day_of_month", Duration(months=1)),
        ("day_of_week", Duration(days=7)),
        ("hour_of_day", Duration(days=1)),
        ("minute_of_hour", Duration(hours=1)),
        ("second_of_minute", Duration(minutes=1)),
    ]
    for prop_name, expected in cases:
        context = Mock(truncated=True)
        context.get_largest_truncated_property_name.return_value = prop_name
        result = parser._get_interval_from_expression(None, context)
        assert result == expected, f"Failed for {prop_name}"

    # when prop_name doesn't match anything, return None
    context = Mock(truncated=True)
    context.get_largest_truncated_property_name.return_value = "unknown_prop"
    assert parser._get_interval_from_expression(None, context) is None


def test_get_min_from_expression_unresolvable(parsers):
    """It should skip points that cannot be resolved (cpoint is None)."""
    parser = parsers[0]

    # "+P1M" with context=None results in cpoint=None (pure offset, no
    # context to resolve against), so it should be skipped.
    # "20000101T0000Z" resolves fine and should be selected as the min.
    result = parser._get_min_from_expression(
        "min(+P1M, 20000101T0000Z)", context=None
    )
    assert result == "20000101T0000Z"


def test_get_point_from_expression_truncated_isodatetime_error(parsers):
    """It should continue past truncated expressions that raise
    IsodatetimeError."""
    parser = parsers[0]

    # "99T25" matches the TRUNCATED_REC_MAP regex ^\d\dT (for "---" prefix),
    # but "---99T25" is not a valid truncated ISO point (no day 99, hour 25),
    # so it raises IsodatetimeError and the loop continues.
    # Nothing else matches, so CylcTimeSyntaxError is ultimately raised.
    with pytest.raises(CylcTimeSyntaxError):
        parser._get_point_from_expression(
            "99T25", context=None, allow_truncated=True
        )
