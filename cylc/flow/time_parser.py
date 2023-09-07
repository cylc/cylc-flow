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
from typing import TYPE_CHECKING, List, Optional, Pattern, Tuple, Union, cast

from metomi.isodatetime.data import Duration, TimeRecurrence
from metomi.isodatetime.exceptions import IsodatetimeError
from metomi.isodatetime.parsers import (
    DurationParser, TimePointParser, TimeRecurrenceParser
)

from cylc.flow import LOG
from cylc.flow.cycling import parse_exclusion
from cylc.flow.exceptions import (
    CylcMissingContextPointError,
    CylcMissingFinalCyclePointError,
    CylcTimeSyntaxError,
)
import cylc.flow.flags

if TYPE_CHECKING:
    from metomi.isodatetime.data import TimePoint
    from cylc.flow.cycling.iso8601 import ISO8601Point


UTC_UTC_OFFSET_HOURS_MINUTES = (0, 0)


class CylcTimeParser:

    """Parser for Cylc abbreviated/full ISO 8601 syntax.

    Arguments:
    context_start_point describes the beginning date/time used for
    extrapolating incomplete date/time syntax (usually initial
    cycle point). It is either a date/time string in full ISO 8601
    syntax or a metomi.isodatetime.data.TimePoint object.
    context_end_point is the same as context_start_point, but describes
    a final time - e.g. the final cycle point.

    """

    POINT_INVALID_FOR_CYLC_REGEXES = [
        (re.compile(r"^\d\d$"),
         ("2 digit centuries not allowed. Did you mean T-digit-digit e.g. "
          "'T00'?"))
    ]

    RECURRENCE_FORMAT_REGEXES: List[Tuple[Pattern, int]] = [
        (re.compile(r"^(?P<start>[^PR/][^/]*)$"), 3),
        (re.compile(r"^R(?P<reps>\d+)?/(?P<start>[^PR/][^/]*)/(?P<end>[^PR/]"
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

    def __init__(
        self,
        context_start_point: Union['ISO8601Point', 'TimePoint', str, None],
        context_end_point: Union['ISO8601Point', 'TimePoint', str, None],
        parsers: Tuple[TimePointParser, DurationParser, TimeRecurrenceParser]
    ):
        if context_start_point is not None:
            context_start_point = str(context_start_point)
        if context_end_point is not None:
            context_end_point = str(context_end_point)
        self.timepoint_parser, self.duration_parser, self.recurrence_parser = (
            parsers
        )

        if isinstance(context_start_point, str):
            context_start_point, _ = self._get_point_from_expression(
                context_start_point, None)
        self.context_start_point: Optional['TimePoint'] = context_start_point
        if isinstance(context_end_point, str):
            context_end_point, _ = self._get_point_from_expression(
                context_end_point, None)
        self.context_end_point: Optional['TimePoint'] = context_end_point

    @staticmethod
    def initiate_parsers(num_expanded_year_digits=0, dump_format=None,
                         assumed_time_zone=None):
        """Initiate datetime parsers required to initiate this class.

        Returns:
            tuple: (timepoint_parser, duration_parser, time_recurrence_parser)
                - timepoint_parser - metomi.isodatetime.parsers.TimePointParser
                  obj.
                - duration_parser - metomi.isodatetime.parsers.DurationParser
                  obj.
                - time_recurrence_parser -
                  metomi.isodatetime.parsers.TimeRecurrenceParser obj
        """

        if dump_format is None:
            if num_expanded_year_digits:
                dump_format = "+XCCYYMMDDThhmmZ"
            else:
                dump_format = "CCYYMMDDThhmmZ"

        timepoint_parser = TimePointParser(
            allow_only_basic=False,
            allow_truncated=True,
            num_expanded_year_digits=num_expanded_year_digits,
            dump_format=dump_format,
            assumed_time_zone=assumed_time_zone
        )

        return (timepoint_parser, DurationParser(), TimeRecurrenceParser())

    def parse_interval(self, expr: str) -> Duration:
        """Parse an interval (duration) in full ISO date/time format."""
        return self.duration_parser.parse(expr)

    def parse_timepoint(
        self, expr: str, context_point: Optional['TimePoint'] = None
    ) -> 'TimePoint':
        """Parse an expression in abbrev. or full ISO date/time format.

        Args:
            expr: a string such as 20010205T00Z, or a truncated/abbreviated
                format string such as T06 or -P2Y.
            context_point: supplies the missing information for truncated
                expressions. E.g. for inter-cycle dependency expressions,
                it should be the task cycle point.
                If None, self.context_start_point is used.

        """
        if context_point is None:
            context_point = self.context_start_point
        point, offsets = self._get_point_from_expression(
            expr, context_point, allow_truncated=True
        )
        if point is not None:
            if point.truncated:
                point += context_point  # type: ignore[operator]
            for offset in offsets:
                point += offset
            return point
        raise CylcTimeSyntaxError(
            ("'%s': not a valid cylc-shorthand or full " % expr) +
            "ISO 8601 date representation")

    def parse_recurrence(
        self,
        expression: str,
        context_start_point: Optional['TimePoint'] = None,
        context_end_point: Optional['TimePoint'] = None,
        zero_duration_warning: bool = True,
    ) -> Tuple[TimeRecurrence, list]:
        """Parse an expression in abbrev. or full ISO recurrence format.

        Args:
            expression:
                The recurrence expression to parse.
            context_start_point:
                Sequence start point from the global context.
            context_end_point:
                Sequence end point from the global context.
            zero_duration_warning:
                If `False`, then zero-duration recurrence warnings will be
                turned off. This is set for exclusion parsing.

        """
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
            start: Optional[str] = result.groupdict().get("start")
            end: Optional[str] = result.groupdict().get("end")
            start_required = (format_num in {1, 3})
            end_required = (format_num in {1, 4})
            start_point, start_offsets = self._get_point_from_expression(
                start, context_start_point,
                is_required=start_required,
                allow_truncated=True
            )
            try:
                end_point, end_offsets = self._get_point_from_expression(
                    end, context_end_point,
                    is_required=end_required,
                    allow_truncated=True
                )
            except CylcMissingContextPointError:
                raise CylcMissingFinalCyclePointError(
                    "This workflow requires a final cycle point."
                )

            exclusion_points = []
            # Convert the exclusion strings to ISO8601 points
            if exclusions is not None:
                for exclusion in exclusions:
                    try:
                        # Attempt to convert to TimePoint
                        exclusion_point, excl_offsets = (
                            self._get_point_from_expression(exclusion, None)
                        )
                        for offset in excl_offsets:
                            exclusion_point += offset  # type: ignore[operator]
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
            elif repetitions == 1:
                interval = Duration(0)
            if start_point is not None:
                if start_point.truncated:
                    start_point += (  # type: ignore[operator]
                        context_start_point
                    )
                for offset in start_offsets:
                    start_point += offset
            if end_point is not None:
                if end_point.truncated:
                    end_point += context_end_point  # type: ignore[operator]
                for offset in end_offsets:
                    end_point += offset

            if (
                interval and
                start_point is None and repetitions is None and
                context_start_point is not None
            ):
                # isodatetime only reverses bounded end-point recurrences.
                # This is unbounded, and will come back in reverse order.
                # We need to reverse it.
                start_point = cast(  # (end pt can't be None if start is None)
                    'TimePoint', end_point
                )
                repetitions = 1
                while start_point > context_start_point:
                    start_point -= interval
                    repetitions += 1
                end_point = None

            if (
                zero_duration_warning
                and not interval
                and repetitions != 1
                and (format_num != 1 or start_point == end_point)
            ):
                LOG.warning(
                    "Cannot have more than 1 repetition for zero-duration "
                    f"recurrence {expression}."
                )

            if cylc.flow.flags.cylc7_back_compat and format_num == 1:
                LOG.warning(
                    f"The recurrence '{expression}' is unlikely to behave "
                    "the same way as in Cylc 7 as that implementation was "
                    "incorrect (see https://cylc.github.io/cylc-doc/stable/"
                    "html/user-guide/writing-workflows/scheduling.html"
                    "#format-1-r-limit-datetime-datetime)"
                )

            return TimeRecurrence(
                repetitions=repetitions,
                start_point=start_point,
                duration=interval,
                end_point=end_point
            ), exclusion_points

        raise CylcTimeSyntaxError("Could not parse %s" % expression)

    def _get_interval_from_expression(
        self, expr: Optional[str], context: Optional['TimePoint'] = None
    ) -> Optional[Duration]:
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
            return Duration(**kwargs)
        return self.duration_parser.parse(expr)

    def _get_min_from_expression(
        self,
        expr: str,
        context: Optional['TimePoint']
    ) -> str:
        points: List[str] = [
            x.strip() for x in re.findall(self.MIN_REGEX, expr)[0].split(",")
        ]
        ptslist: List['TimePoint'] = []
        min_entry = ""
        for point in points:
            cpoint, offsets = self._get_point_from_expression(
                point, context, allow_truncated=True
            )
            if cpoint is not None:
                if cpoint.truncated:
                    cpoint += context  # type: ignore[operator]
                for offset in offsets:
                    cpoint += offset
                ptslist.append(cpoint)
                if cpoint == min(ptslist):
                    min_entry = point
        return min_entry

    def _get_point_from_expression(
        self,
        expr: Optional[str],
        context: Optional['TimePoint'],
        is_required: bool = False,
        allow_truncated: bool = False
    ) -> Tuple[Optional['TimePoint'], List[Duration]]:
        """Gets a TimePoint from an expression"""
        if expr is None:
            if is_required and allow_truncated:
                if context is None:
                    raise CylcMissingContextPointError(
                        "Missing context cycle point."
                    )
                return context, []
            return None, []

        if expr.startswith("min("):
            expr = self._get_min_from_expression(expr, context)

        expr_offsets: List[Duration] = []
        if self.OFFSET_REGEX.search(expr):
            expr, expr_offsets = self.parse_chain_expression(expr)
        if not expr and allow_truncated:
            return context, expr_offsets

        for invalid_rec, msg in self.POINT_INVALID_FOR_CYLC_REGEXES:
            if invalid_rec.search(expr):
                raise CylcTimeSyntaxError(f"'{expr}': {msg}")

        expr_to_parse = expr
        if expr.endswith("T"):
            expr_to_parse += "00"
        try:
            expr_point: 'TimePoint' = self.timepoint_parser.parse(
                expr_to_parse
            )
        except ValueError:  # not IsodatetimeError as too specific
            pass
        else:
            return expr_point, expr_offsets

        if allow_truncated:
            for truncation_string, recs in self.TRUNCATED_REC_MAP.items():
                for rec in recs:
                    if rec.search(expr):
                        try:
                            expr_point = self.timepoint_parser.parse(
                                truncation_string + expr_to_parse)
                        except IsodatetimeError:
                            continue
                        return expr_point, expr_offsets

        raise CylcTimeSyntaxError(
            f"'{expr}': not a valid cylc-shorthand or full "
            "ISO 8601 date representation"
        )

    def parse_chain_expression(self, expr: str) -> Tuple[str, List[Duration]]:
        """Parse an expression such as '+P1M+P1D'.

        Returns:
            Expression: The expression with any offsets removed.
            Offsets: List of offsets from the expression. Note: by keeping
                offsets separate (rather than combine into 1 Duration),
                we preserve order of operations.

        Examples:
            >>> ctp = CylcTimeParser(
            ...    None, None, (TimePointParser(), DurationParser(), None)
            ... )
            >>> expr, offsets = ctp.parse_chain_expression('2022+P1M-P1D')
            >>> expr
            '2022'
            >>> [str(i) for i in offsets]
            ['P1M', '-P1D']
        """
        expr_offsets: List[Duration] = []
        chain_expr: List[str] = self.CHAIN_REGEX.findall(expr)
        expr = ""
        for item in chain_expr:
            if "P" not in item:
                expr += item
                continue
            split_expr = self.OFFSET_REGEX.split(item)
            expr += split_expr.pop(0)
            expr_offset_item = self.duration_parser.parse(item[1:])
            if item[0] == "-":
                expr_offset_item *= -1
            expr_offsets.append(expr_offset_item)
        return expr, expr_offsets
