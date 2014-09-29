#!/usr/bin/env python
# -*- coding: utf-8 -*-
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""This module is for parsing date/time representations.

Expressions can be formatted in either the full ISO 8601:2004 date/time
representations (also including the ISO 8601:2000 truncated syntax), or
in the Cylc-specific abbreviations thereof.

Where abbreviations or truncations are used, the missing information
needs to be filled in by some date/time context - this means that "T06"
needs to be applied to a context time such as "20201205T0000Z" in order
to get a full date/time (in this example, "20201205T0600Z"). This
context is the initial cycle point or final cycle point for the task
cycling dependency graph section specification, and is the task cycle
time for inter-cycle task references such as "foo[-P6Y] => foo".

"""

import re
import unittest

import cylc.CylcError
import isodatetime.data
import isodatetime.parsers


UTC_UTC_OFFSET_HOURS_MINUTES = (0, 0)


class CylcTimeSyntaxError(cylc.CylcError.CylcError):

    """An error denoting invalid ISO/Cylc input syntax."""


class CylcMissingContextPointError(cylc.CylcError.CylcError):

    """An error denoting a missing (but required) context cycle point."""


class CylcMissingFinalCyclePointError(cylc.CylcError.CylcError):

    """An error denoting a missing (but required) final cycle point."""


class CylcTimeParser(object):

    """Parser for Cylc abbreviated/full ISO 8601 syntax.

    Arguments:
    context_start_point describes the beginning date/time used for
    extrapolating incomplete date/time syntax (usually initial
    cycle point). It is either a date/time string in full ISO 8601
    syntax or an isodatetime.data.TimePoint object.
    context_end_point is the same as context_start_point, but describes
    a final time - e.g. the final cycle point.

    """

    POINT_INVALID_FOR_CYLC_REGEXES = [
        (r"^\d\d$", ("2 digit centuries not allowed. " +
                     "Did you mean T-digit-digit e.g. 'T00'?")
        )
    ]

    RECURRENCE_FORMAT_REGEXES = [
        (r"^(?P<start>[^PR/][^/]*)$", 3),
        (r"^R(?P<reps>\d+)/(?P<start>[^PR/][^/]*)/(?P<end>[^PR/][^/]*)$", 1),
        (r"^(?P<start>[^PR/][^/]*)/(?P<intv>P[^/]*)/?$", 3),
        (r"^(?P<intv>P[^/]*)$", 3),
        (r"^(?P<intv>P[^/]*)/(?P<end>[^PR/][^/]*)$", 4),
        (r"^R(?P<reps>\d+)?/(?P<start>[^PR/][^/]*)/?$", 3),
        (r"^R(?P<reps>\d+)?/(?P<start>[^PR/][^/]*)/(?P<intv>P[^/]*)$", 3),
        (r"^R(?P<reps>\d+)?/(?P<start>)/(?P<intv>P[^/]*)$", 3),
        (r"^R(?P<reps>\d+)?/(?P<intv>P[^/]*)/(?P<end>[^PR/][^/]*)$", 4),
        (r"^R(?P<reps>\d+)?/(?P<intv>P[^/]*)/?$", 4),
        (r"^R(?P<reps>\d+)?//(?P<end>[^PR/][^/]*)$", 4),
        (r"^R(?P<reps>1)/?(?P<start>$)", 3),
        (r"^R(?P<reps>1)//(?P<end>[^PR/][^/]*)$", 4)
    ]

    CHAIN_REGEX = '((?:[+-P]|[\dT])[\d\w]*)'

    OFFSET_REGEX = r"(?P<sign>[+-])(?P<intv>P.+)$"

    TRUNCATED_REC_MAP = {"---": [re.compile("^\d\dT")],
                         "--": [re.compile("^\d\d\d\dT")],
                         "-": [re.compile("^\d\d\dT"),
                               re.compile("\dW\d\dT"),
                               re.compile("W\d\d\d?T"),
                               re.compile("W-\dT")]}

    def __init__(self, context_start_point,
                 context_end_point, num_expanded_year_digits=0,
                 dump_format=None,
                 custom_point_parse_function=None,
                 assumed_time_zone=None):
        if context_start_point is not None:
            context_start_point = str(context_start_point)
        if context_end_point is not None:
            context_end_point = str(context_end_point)
        self.num_expanded_year_digits = num_expanded_year_digits
        if dump_format is None:
            if num_expanded_year_digits:
                dump_format = u"+XCCYYMMDDThhmmZ"
            else:
                dump_format = "CCYYMMDDThhmmZ"
            
        self.timepoint_parser = isodatetime.parsers.TimePointParser(
            allow_only_basic=False, # TODO - Ben: why was this set True
            allow_truncated=True,
            num_expanded_year_digits=num_expanded_year_digits,
            dump_format=dump_format,
            assumed_time_zone=assumed_time_zone
        )
        self._recur_format_recs = []
        for regex, format_num in self.RECURRENCE_FORMAT_REGEXES:
            self._recur_format_recs.append((re.compile(regex), format_num))
        self._offset_rec = re.compile(self.OFFSET_REGEX)
        self._invalid_point_recs = [
            (re.compile(regex), msg) for (regex, msg) in
            self.POINT_INVALID_FOR_CYLC_REGEXES
        ]
        self.custom_point_parse_function = custom_point_parse_function
        if isinstance(context_start_point, basestring):
            context_start_point, offset = self._get_point_from_expression(
                context_start_point, None)
        self.context_start_point = context_start_point
        if isinstance(context_end_point, basestring):
            context_end_point, offset = self._get_point_from_expression(
                context_end_point, None)
        self.context_end_point = context_end_point
        self.duration_parser = isodatetime.parsers.DurationParser()
        self.recurrence_parser = isodatetime.parsers.TimeRecurrenceParser(
                        timepoint_parser=self.timepoint_parser)

    def parse_interval(self, expr):
        """Parse an interval (duration) in full ISO date/time format."""
        return self.duration_parser.parse(expr)

    def parse_timepoint(self, expr, context_point=None):
        """Parse an expression in abbrev. or full ISO date/time format.

        expression should be a string such as 20010205T00Z, or a
        truncated/abbreviated format string such as T06 or -P2Y.
        context_point should be an isodatetime.data.TimePoint object
        that supplies the missing information for truncated
        expressions. For example, context_point should be the task
        cycle point for inter-cycle dependency expressions. If
        context_point is None, self.context_start_point is used.

        """
        if context_point is None:
            context_point = self.context_start_point
        point, offset = self._get_point_from_expression(
                                                  expr, context_point,
                                                  allow_truncated=True)
        if point is not None:
            if point.truncated:
                point += context_point
            if offset is not None:
                point += offset
            return point
        raise CylcTimeSyntaxError(
                    ("'%s': not a valid cylc-shorthand or full " % expr) +
                     "ISO 8601 date representation")

    def parse_recurrence(self, expression,
                         context_start_point=None,
                         context_end_point=None):
        """Parse an expression in abbrev. or full ISO recurrence format."""
        if context_start_point is None:
            context_start_point = self.context_start_point
        if context_end_point is None:
            context_end_point = self.context_end_point
        for rec_object, format_num in self._recur_format_recs:
            result = rec_object.search(expression)
            if not result:
                continue
            props = {}
            repetitions = result.groupdict().get("reps")
            if repetitions is not None:
                repetitions = int(repetitions)
            start = result.groupdict().get("start")
            end = result.groupdict().get("end")
            start_required = (format_num in [1, 3])
            end_required = (format_num in [1, 4])
            start_point, start_offset = self._get_point_from_expression(
                start, context_start_point,
                is_required=start_required,
                allow_truncated=True
            )
            try:
                end_point, end_offset = self._get_point_from_expression(
                    end, context_end_point,
                    is_required=end_required,
                    allow_truncated=True
                )
            except CylcMissingContextPointError:
                raise CylcMissingFinalCyclePointError(
                    "This suite requires a final cycle point."
                )
            intv = result.groupdict().get("intv")
            intv_context_truncated_point = None
            if start_point is not None and start_point.truncated:
                intv_context_truncated_point = start_point
            if end_point is not None and end_point.truncated:
                intv_context_truncated_point = end_point
            interval = self._get_interval_from_expression(
                             intv, context=intv_context_truncated_point)
            if format_num == 1:
                interval = None
            if repetitions == 1:
                # Set arbitrary interval (does not matter).
                interval = self.duration_parser.parse("P0Y")
            if start_point is not None:
                if start_point.truncated:
                    start_point += context_start_point
                if start_offset is not None:
                    start_point += start_offset
            if end_point is not None:
                if end_point.truncated:
                    end_point += context_end_point
                if end_offset is not None:
                    end_point += end_offset

            if (start_point is None and repetitions is None and
                   interval is not None and
                   context_start_point is not None):
                # isodatetime only reverses bounded end-point recurrences.
                # This is unbounded, and will come back in reverse order.
                # We need to reverse it.
                start_point = end_point
                while start_point > context_start_point:
                    start_point -= interval
                end_point = None

            return isodatetime.data.TimeRecurrence(
                repetitions=repetitions,
                start_point=start_point,
                duration=interval,
                end_point=end_point
            )         
            
        raise CylcTimeSyntaxError("Could not parse %s" % expression)

    def _get_interval_from_expression(self, expr, context=None):
        if expr is None:
            if context is None or not context.truncated:
                return None
            prop_name = context.get_largest_truncated_property_name()
            kwargs = {}
            if prop_name == "year_of_century":
                kwargs = {"years": 100}
            if prop_name == "year_of_decade":
                kwargs = {"years": 10}
            if prop_name in ["month_of_year", "week_of_year", "day_of_year"]:
                kwargs = {"years": 1}
            if prop_name == "day_of_month":
                kwargs = {"months": 1}
            if prop_name == "day_of_week":
                kwargs = {"days": 7}
            if prop_name == "hour_of_day":
                kwargs = {"days": 1}
            if prop_name == "minute_of_hour":
                kwargs = {"hours": 1}
            if prop_name == "second_of_minute":
                kwargs = {"minutes": 1}
            if not kwargs:
                return None
            return isodatetime.data.Duration(**kwargs)
        return self.duration_parser.parse(expr)

    def _get_point_from_expression(self, expr, context, is_required=False,
                                   allow_truncated=False):
        if expr is None:
            if is_required and allow_truncated:
                if context is None:
                    raise CylcMissingContextPointError(
                        "Missing context cycle point."
                    )
                return context.copy(), None
            return None, None
        expr_point = None
        expr_offset = None
        if self._offset_rec.search(expr):
            chain_expr = re.findall(self.CHAIN_REGEX, expr)
            expr = ""
            for item in chain_expr:
                if not "P" in item:
                    expr += item
                    continue
                split_expr = self._offset_rec.split(item)
                expr += split_expr.pop(0)
                if split_expr[1] == "+":
                    split_expr.pop(1)
                expr_offset_item = "".join(split_expr[1:])
                expr_offset_item = self.duration_parser.parse(
                                                item[1:])
                if item[0] == "-":
                    expr_offset_item *= -1
                if not expr_offset:
                    expr_offset = expr_offset_item
                else:
                    expr_offset = expr_offset + expr_offset_item
        if not expr and allow_truncated:
            return context.copy(), expr_offset
        for invalid_rec, msg in self._invalid_point_recs:
            if invalid_rec.search(expr):
                raise CylcTimeSyntaxError("'%s': %s" % (expr, msg))
        expr_to_parse = expr
        if expr.endswith("T"):
            expr_to_parse = expr + "00"
        parse_function = self.timepoint_parser.parse
        if self.custom_point_parse_function is not None:
            parse_function = self.custom_point_parse_function
        try:
            expr_point = parse_function(expr_to_parse)
        except ValueError:
            pass
        else:
            return expr_point, expr_offset
        if allow_truncated:
            for truncation_string, recs in self.TRUNCATED_REC_MAP.items():
                for rec in recs:
                    if rec.search(expr):
                        try:
                            expr_point = parse_function(
                                truncation_string + expr_to_parse)
                        except ValueError:
                            continue
                        return expr_point, expr_offset
        raise CylcTimeSyntaxError(
                  ("'%s': not a valid cylc-shorthand or full " % expr) +
                  "ISO 8601 date representation")


class TestRecurrenceSuite(unittest.TestCase):

    """Test Cylc recurring date/time syntax parsing."""

    def setUp(self):
        self._start_point = "19991226T0930Z"
        # Note: the following timezone will be Z-ified *after* truncation
        # or offsets are applied. 
        self._end_point = "20010506T1200+0200"
        self._parsers = {
            0: CylcTimeParser(
                self._start_point, self._end_point,
                assumed_time_zone=UTC_UTC_OFFSET_HOURS_MINUTES
            ),
            2: CylcTimeParser(
                self._start_point, self._end_point,
                num_expanded_year_digits=2,
                assumed_time_zone=UTC_UTC_OFFSET_HOURS_MINUTES
            )
        }

    def test_first_recurrence_format(self):
        """Test the first ISO 8601 recurrence format."""
        tests = [("R5/T06/04T1230-0300",
                  0,
                  "R5/19991227T0600Z/20010604T1530Z",
                  ["19991227T0600Z", "20000506T1422Z",
                   "20000914T2245Z", "20010124T0707Z",
                   "20010604T1530Z"]),
                 ("R2/-0450000101T04Z/+0020630405T2200-05",
                  2,
                  "R2/-0450000101T0400Z/+0020630406T0300Z",
                  ["-0450000101T0400Z", "+0020630406T0300Z"]),
                 ("R10/T12+P10D/-P1Y",
                  0,
                  "R10/20000105T1200Z/20000506T1000Z",
                  ["20000105T1200Z", "20000119T0106Z",
                   "20000201T1413Z", "20000215T0320Z",
                   "20000228T1626Z", "20000313T0533Z",
                   "20000326T1840Z", "20000409T0746Z",
                   "20000422T2053Z", "20000506T1000Z"])]
        for test in tests:
            if len(test) == 3:
                expression, num_expanded_year_digits, ctrl_data = test
                ctrl_results = None
            else:
                expression, num_expanded_year_digits, ctrl_data = test[:3]
                ctrl_results = test[3]
            parser = self._parsers[num_expanded_year_digits]
            recurrence = parser.parse_recurrence(expression)
            test_data = str(recurrence)
            self.assertEqual(test_data, ctrl_data)
            if ctrl_results is None:
                continue
            test_results = []
            for i, test_result in enumerate(recurrence):
                self.assertEqual(str(test_result), ctrl_results[i])
                test_results.append(str(test_result))
            self.assertEqual(test_results, ctrl_results)

    def test_third_recurrence_format(self):
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
            recurrence = self._parsers[0].parse_recurrence(expression)
            test_data = str(recurrence)
            self.assertEqual(test_data, ctrl_data)
            if ctrl_results is None:
                continue
            test_results = []
            for i, test_result in enumerate(recurrence):
                if i > len(ctrl_results) - 1:
                    break
                self.assertEqual(str(test_result), ctrl_results[i])
                test_results.append(str(test_result))
            self.assertEqual(test_results, ctrl_results)

    def test_fourth_recurrence_format(self):
        """Test the fourth ISO 8601 recurrence format."""
        tests = [("PT6H/20000101T0500Z", "R/PT6H/20000101T0500Z"),
                 ("P12D/+P2W", "R/P12D/20010520T1000Z"),
                 ("P1W/-P1M1D", "R/P1W/20010405T1000Z"),
                 ("P6D/T12+02", "R/P6D/20010506T1000Z"),
                 ("P6DT12H/01T00+02", "R/P6DT12H/20010531T2200Z"),
                 ("R/P1D/20010506T1200+0200", "R/P1D/20010506T1000Z"),
                 ("R/PT5M/+PT2M", "R/PT5M/20010506T1002Z"),
                 ("R/P20Y/-P20Y", "R/P20Y/19810506T1000Z"),
                 ("R/P3YT2H/T18-02", "R/P3YT2H/20010506T2000Z"),
                 ("R/PT3H/31T", "R/PT3H/20010531T0000Z"),
                 ("R5/P1Y/", "R5/P1Y/20010506T1000Z"),
                 ("R3/P2Y/02T", "R3/P2Y/20010602T0000Z"),
                 ("R/P2Y", "R/P2Y/20010506T1000Z"),
                 ("R48/PT2H", "R48/PT2H/20010506T1000Z"),
                 ("R/P21Y/", "R/P21Y/20010506T1000Z")]
        for test in tests:
            if len(test) == 2:
                expression, ctrl_data = test
                ctrl_results = None
            else:
                expression, ctrl_data, ctrl_results = test
            recurrence = self._parsers[0].parse_recurrence(expression)
            test_data = str(recurrence)
            self.assertEqual(test_data, ctrl_data)
            if ctrl_results is None:
                continue
            test_results = []
            for i, test_result in enumerate(recurrence):
                self.assertEqual(str(test_result), ctrl_results[i])
                test_results.append(str(test_result))
            self.assertEqual(test_results, ctrl_results)

    def test_inter_cycle_timepoints(self):
        """Test the inter-cycle point parsing."""
        task_cycle_time = self._parsers[0].parse_timepoint(
                                "20000101T00Z")
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
            parser = self._parsers[num_expanded_year_digits]
            test_data = str(parser.parse_timepoint(
                                  expression,
                                  context_point=task_cycle_time))
            self.assertEqual(test_data, ctrl_data)

    def test_interval(self):
        """Test the interval timepoint parsing (purposefully weak tests)."""
        tests = ["PT6H2M", "PT6H", "P2Y5D",
                 "P5W", "PT12M2S", "PT65S",
                 "PT2M", "P1YT567,4M"]
        for expression in tests:
            test_data = str(self._parsers[0].parse_interval(expression))
            self.assertEqual(test_data, expression)


if __name__ == "__main__":
    unittest.main()
