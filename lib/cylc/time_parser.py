#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import isodatetime.data
import isodatetime.parsers

from cylc.cycling import parse_exclusion
from cylc.exceptions import (
    CylcTimeSyntaxError, CylcMissingContextPointError,
    CylcMissingFinalCyclePointError)


UTC_UTC_OFFSET_HOURS_MINUTES = (0, 0)


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
        (re.compile(r"^\d\d$"),
         ("2 digit centuries not allowed. Did you mean T-digit-digit e.g. "
          "'T00'?"))
    ]

    RECURRENCE_FORMAT_REGEXES = [
        (re.compile(r"^(?P<start>[^PR/][^/]*)$"), 3),
        (re.compile(r"^R(?P<reps>\d+)/(?P<start>[^PR/][^/]*)/(?P<end>[^PR/]"
                    "[^/]*)$"), 1),
        (re.compile(r"^(?P<start>[^PR/][^/]*)/(?P<intv>P[^/]*)/?$"), 3),
        (re.compile(r"^(?P<intv>P[^/]*)$"), 3),
        (re.compile(r"^(?P<intv>P[^/]*)/(?P<end>[^PR/][^/]*)$"), 4),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<start>[^PR/][^/]*)/?$"), 3),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<start>[^PR/][^/]*)/(?P<intv>P[^/]"
                    "*)$"), 3),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<start>)/(?P<intv>P[^/]*)$"), 3),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<intv>P[^/]*)/(?P<end>[^PR/][^/]*)"
                    "$"), 4),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<intv>P[^/]*)/?$"), 4),
        (re.compile(r"^R(?P<reps>\d+)?//(?P<end>[^PR/][^/]*)$"), 4),
        (re.compile(r"^R(?P<reps>1)/?(?P<start>$)"), 3),
        (re.compile(r"^R(?P<reps>1)//(?P<end>[^PR/][^/]*)$"), 4)
    ]

    CHAIN_REGEX = re.compile(r'((?:[+-P]|[\dT])[\d\w]*)')

    MIN_REGEX = re.compile(r'min\(([^)]+)\)')

    OFFSET_REGEX = re.compile(r"(?P<sign>[+-])(?P<intv>P.+)$")

    TRUNCATED_REC_MAP = {
        "---": [re.compile(r"^\d\dT")],
        "--": [re.compile(r"^\d\d\d\dT")],
        "-": [
            re.compile(r"^\d\d\dT"),
            re.compile(r"\dW\d\dT"),
            re.compile(r"W\d\d\d?T"),
            re.compile(r"W-\dT"),
            re.compile(r"W-\d")
        ]
    }

    __slots__ = ('timepoint_parser', 'duration_parser', 'recurrence_parser',
                 'context_start_point', 'context_end_point')

    def __init__(self, context_start_point, context_end_point, parsers):
        if context_start_point is not None:
            context_start_point = str(context_start_point)
        if context_end_point is not None:
            context_end_point = str(context_end_point)
        self.timepoint_parser, self.duration_parser, self.recurrence_parser = (
            parsers)

        if isinstance(context_start_point, str):
            context_start_point = self._get_point_from_expression(
                context_start_point, None)[0]
        self.context_start_point = context_start_point
        if isinstance(context_end_point, str):
            context_end_point = self._get_point_from_expression(
                context_end_point, None)[0]
        self.context_end_point = context_end_point

    @staticmethod
    def initiate_parsers(num_expanded_year_digits=0, dump_format=None,
                         assumed_time_zone=None):
        """Initiate datetime parsers required to initiate this class.

        Returns:
            tuple: (timepoint_parser, duration_parser, time_recurrence_parser)
                - timepoint_parser - isodatetime.parsers.TimePointParser obj.
                - duration_parser - isodatetime.parsers.DurationParser obj.
                - time_recurrence_parser -
                  isodatetime.parsers.TimeRecurrenceParser obj
        """

        if dump_format is None:
            if num_expanded_year_digits:
                dump_format = "+XCCYYMMDDThhmmZ"
            else:
                dump_format = "CCYYMMDDThhmmZ"

        timepoint_parser = isodatetime.parsers.TimePointParser(
            allow_only_basic=False,
            allow_truncated=True,
            num_expanded_year_digits=num_expanded_year_digits,
            dump_format=dump_format,
            assumed_time_zone=assumed_time_zone
        )

        return (timepoint_parser,
                isodatetime.parsers.DurationParser(),
                isodatetime.parsers.TimeRecurrenceParser()
                )

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
            expr, context_point, allow_truncated=True)
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
        expression, exclusions = parse_exclusion(str(expression))

        if context_start_point is None:
            context_start_point = self.context_start_point
        if context_end_point is None:
            context_end_point = self.context_end_point
        for rec_object, format_num in self.RECURRENCE_FORMAT_REGEXES:
            result = rec_object.search(expression)
            if not result:
                continue

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

            exclusion_point = None
            exclusion_points = []
            # Convert the exclusion strings to ISO8601 points
            if exclusions is not None:
                for exclusion in exclusions:
                    try:
                        # Attempt to convert to TimePoint
                        exclusion_point, excl_off = (
                            self._get_point_from_expression(
                                exclusion, None, is_required=False,
                                allow_truncated=False))
                        if excl_off:
                            exclusion_point += excl_off
                        exclusion_points.append(exclusion_point)
                    except (CylcTimeSyntaxError, IndexError):
                        # Not a point, parse it as recurrence later
                        exclusion_points.append(exclusion)

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
                repetitions = 1
                while start_point > context_start_point:
                    start_point -= interval
                    repetitions += 1
                end_point = None

            return isodatetime.data.TimeRecurrence(
                repetitions=repetitions,
                start_point=start_point,
                duration=interval,
                end_point=end_point
            ), exclusion_points

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

    def _get_min_from_expression(self, expr, context):
        points = [x.strip()
                  for x in re.findall(self.MIN_REGEX, expr)[0].split(",")]
        ptslist = []
        min_entry = ""
        for point in points:
            cpoint, offset = self._get_point_from_expression(
                point, context, allow_truncated=True)
            if cpoint is not None:
                if cpoint.truncated:
                    cpoint += context
                if offset is not None:
                    cpoint += offset
            ptslist.append(cpoint)
            if cpoint == min(ptslist):
                min_entry = point
        return min_entry

    def _get_point_from_expression(self, expr, context, is_required=False,
                                   allow_truncated=False):
        """Gets a TimePoint from an expression"""
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

        if expr.startswith("min("):
            expr = self._get_min_from_expression(expr, context)

        if self.OFFSET_REGEX.search(expr):
            chain_expr = self.CHAIN_REGEX.findall(expr)
            expr = ""
            for item in chain_expr:
                if "P" not in item:
                    expr += item
                    continue
                split_expr = self.OFFSET_REGEX.split(item)
                expr += split_expr.pop(0)
                if split_expr[1] == "+":
                    split_expr.pop(1)
                expr_offset_item = "".join(split_expr[1:])
                expr_offset_item = self.duration_parser.parse(item[1:])
                if item[0] == "-":
                    expr_offset_item *= -1
                if not expr_offset:
                    expr_offset = expr_offset_item
                else:
                    expr_offset = expr_offset + expr_offset_item
        if not expr and allow_truncated:
            return context.copy(), expr_offset
        for invalid_rec, msg in self.POINT_INVALID_FOR_CYLC_REGEXES:
            if invalid_rec.search(expr):
                raise CylcTimeSyntaxError("'%s': %s" % (expr, msg))
        expr_to_parse = expr
        if expr.endswith("T"):
            expr_to_parse = expr + "00"
        try:
            expr_point = self.timepoint_parser.parse(expr_to_parse)
        except ValueError:
            pass
        else:
            return expr_point, expr_offset
        if allow_truncated:
            for truncation_string, recs in self.TRUNCATED_REC_MAP.items():
                for rec in recs:
                    if rec.search(expr):
                        try:
                            expr_point = self.timepoint_parser.parse(
                                truncation_string + expr_to_parse)
                        except ValueError:
                            continue
                        return expr_point, expr_offset
        raise CylcTimeSyntaxError(
            ("'%s': not a valid cylc-shorthand or full " % expr) +
            "ISO 8601 date representation")
