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

"""Date-time cycling by point, interval, and sequence classes."""

import contextlib
from functools import lru_cache
import re
from typing import List, Optional, TYPE_CHECKING, Tuple

from metomi.isodatetime.data import Calendar, CALENDAR, Duration
from metomi.isodatetime.dumpers import TimePointDumper
from metomi.isodatetime.timezone import (
    get_local_time_zone, get_local_time_zone_format, TimeZoneFormatMode)
from metomi.isodatetime.exceptions import IsodatetimeError
from cylc.flow.time_parser import CylcTimeParser
from cylc.flow.cycling import (
    PointBase, IntervalBase, SequenceBase, ExclusionBase, cmp
)
from cylc.flow.exceptions import (
    CylcConfigError,
    IntervalParsingError,
    PointParsingError,
    SequenceDegenerateError
)
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.parsec.validate import IllegalValueError

if TYPE_CHECKING:
    from metomi.isodatetime.data import TimePoint
    from metomi.isodatetime.parsers import (
        DurationParser, TimePointParser, TimeRecurrenceParser)

CYCLER_TYPE_ISO8601 = "iso8601"
CYCLER_TYPE_SORT_KEY_ISO8601 = 1

DATE_TIME_FORMAT = "CCYYMMDDThhmm"
EXPANDED_DATE_TIME_FORMAT = "+XCCYYMMDDThhmm"
NEW_DATE_TIME_REC = re.compile("T")

WARNING_PARSE_EXPANDED_YEAR_DIGITS = (
    "(incompatible with [cylc]cycle point num expanded year digits = %s ?)")


class WorkflowSpecifics:

    """Store workflow-setup-specific constants and utilities here."""
    ASSUMED_TIME_ZONE: Tuple[int, int]
    DUMP_FORMAT: str
    abbrev_util: CylcTimeParser
    interval_parser: 'DurationParser'
    point_parser: 'TimePointParser'
    recurrence_parser: 'TimeRecurrenceParser'
    iso8601_parsers: Tuple[
        'TimePointParser', 'DurationParser', 'TimeRecurrenceParser'
    ]
    NUM_EXPANDED_YEAR_DIGITS: int = 0


class ISO8601Point(PointBase):

    """A single point in an ISO8601 date time sequence."""

    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601

    __slots__ = ('value')

    @classmethod
    def from_nonstandard_string(cls, point_string):
        """Standardise a date-time string."""
        return ISO8601Point(str(point_parse(point_string))).standardise()

    def add(self, other):
        """Add an Interval to self."""
        return ISO8601Point(self._iso_point_add(self.value, other.value))

    def standardise(self):
        """Reformat self.value into a standard representation."""
        try:
            self.value = str(point_parse(self.value))
        except IsodatetimeError as exc:
            if self.value.startswith("+") or self.value.startswith("-"):
                message = WARNING_PARSE_EXPANDED_YEAR_DIGITS % (
                    WorkflowSpecifics.NUM_EXPANDED_YEAR_DIGITS)
            else:
                message = str(exc)
            raise PointParsingError(type(self), self.value, message)
        return self

    def sub(self, other):
        """Subtract a Point or Interval from self."""
        if isinstance(other, ISO8601Point):
            return ISO8601Interval(
                self._iso_point_sub_point(self.value, other.value))
        return ISO8601Point(
            self._iso_point_sub_interval(self.value, other.value))

    @staticmethod
    @lru_cache(10000)
    def _iso_point_add(point_string, interval_string):
        """Add the parsed point_string to the parsed interval_string."""
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point + interval)

    def _cmp(self, other: 'ISO8601Point') -> int:
        return self._iso_point_cmp(self.value, other.value)

    @staticmethod
    @lru_cache(10000)
    def _iso_point_cmp(point_string, other_point_string):
        """Compare the parsed point_string to the other one."""
        point = point_parse(point_string)
        other_point = point_parse(other_point_string)
        return cmp(point, other_point)

    @staticmethod
    @lru_cache(10000)
    def _iso_point_sub_interval(point_string, interval_string):
        """Return the parsed point_string minus the parsed interval_string."""
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point - interval)

    @staticmethod
    @lru_cache(10000)
    def _iso_point_sub_point(point_string, other_point_string):
        """Return the difference between the two parsed point strings."""
        point = point_parse(point_string)
        other_point = point_parse(other_point_string)
        return str(point - other_point)


class ISO8601Interval(IntervalBase):

    """The interval between points in an ISO8601 date time sequence."""

    NULL_INTERVAL_STRING = "P0Y"
    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601

    __slots__ = ('value')

    @classmethod
    def get_null(cls):
        """Return a null interval."""
        return ISO8601Interval("P0Y")

    @classmethod
    def get_null_offset(cls):
        """Return a null offset."""
        return ISO8601Interval("+P0Y")

    def standardise(self):
        """Format self.value into a standard representation."""
        try:
            self.value = str(interval_parse(self.value))
        except IsodatetimeError:
            raise IntervalParsingError(type(self), self.value)
        return self

    def add(self, other):
        """Add other to self (point or interval) c.f. ISO 8601."""
        if isinstance(other, ISO8601Interval):
            return ISO8601Interval(
                self._iso_interval_add(self.value, other.value))
        return other + self

    def _cmp(self, other: 'IntervalBase') -> int:
        """Compare another interval with this one."""
        return self._iso_interval_cmp(self.value, other.value)

    def sub(self, other):
        """Subtract another interval from this one."""
        return ISO8601Interval(
            self._iso_interval_sub(self.value, other.value))

    def __abs__(self):
        """Return an interval with absolute values of this one's values."""
        return ISO8601Interval(
            self._iso_interval_abs(self.value, self.NULL_INTERVAL_STRING))

    def __mul__(self, factor):
        """Return an interval with v * factor for v in this one's values."""
        return ISO8601Interval(self._iso_interval_mul(self.value, factor))

    def __bool__(self):
        """Return whether this interval has any non-null values."""
        return self._iso_interval_nonzero(self.value)

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_abs(interval_string, other_interval_string):
        """Return the absolute (non-negative) value of an interval_string."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        if interval < other:
            return str(interval * -1)
        return interval_string

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_add(interval_string, other_interval_string):
        """Return one parsed interval_string plus the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval + other)

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_cmp(interval_string, other_interval_string):
        """Compare one parsed interval_string with the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return cmp(interval, other)

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_sub(interval_string, other_interval_string):
        """Subtract one parsed interval_string from the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval - other)

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_mul(interval_string, factor):
        """Multiply one parsed interval_string's values by factor."""
        interval = interval_parse(interval_string)
        return str(interval * factor)

    @staticmethod
    @lru_cache(10000)
    def _iso_interval_nonzero(interval_string):
        """Return whether the parsed interval_string is a null interval."""
        interval = interval_parse(interval_string)
        return bool(interval)


class ISO8601Exclusions(ExclusionBase):
    """A collection of ISO8601Sequences that represent excluded sequences.

    The object is able to determine if points are within any of its
    grouped exclusion sequences. The Python ``in`` and ``not in`` operators
    may be used on this object to determine if a point is in the collection
    of exclusion sequences."""

    def __init__(self, excl_points, start_point, end_point=None):
        super(ISO8601Exclusions, self).__init__(start_point, end_point)
        self.build_exclusions(excl_points)

    def build_exclusions(self, excl_points):
        for point in excl_points:
            try:
                # Try making an ISO8601Sequence
                exclusion = ISO8601Sequence(point, self.exclusion_start_point,
                                            self.exclusion_end_point)
                self.exclusion_sequences.append(exclusion)
            except (AttributeError, TypeError, ValueError):
                # Try making an ISO8601Point
                exclusion_point = ISO8601Point.from_nonstandard_string(
                    str(point)) if point else None
                if exclusion_point not in self.exclusion_points:
                    self.exclusion_points.append(exclusion_point)


class ISO8601Sequence(SequenceBase):

    """A sequence of ISO8601 date time points separated by an interval.
    Note that an ISO8601Sequence object (may) contain
    ISO8601ExclusionSequences"""

    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601
    _MAX_CACHED_POINTS = 100

    __slots__ = ('dep_section', 'context_start_point', 'context_end_point',
                 'offset', '_cached_first_point_values',
                 '_cached_next_point_values', '_cached_valid_point_booleans',
                 '_cached_recent_valid_points', 'spec', 'abbrev_util',
                 'recurrence', 'exclusions', 'step', 'value', 'is_on_sequence')

    @classmethod
    def get_async_expr(cls, start_point=None):
        """Express a one-off sequence at the initial cycle point."""
        if start_point is None:
            return "R1"
        return "R1/" + str(start_point)

    def __init__(self, dep_section, context_start_point=None,
                 context_end_point=None):
        SequenceBase.__init__(
            self, dep_section, context_start_point, context_end_point)
        self.dep_section = dep_section

        # cache is_on_sequence
        # see B019 - https://github.com/PyCQA/flake8-bugbear#list-of-warnings
        self.is_on_sequence = lru_cache(maxsize=100)(self._is_on_sequence)

        if (
            context_start_point is None
            or isinstance(context_start_point, ISO8601Point)
        ):
            self.context_start_point = context_start_point
        else:
            self.context_start_point = ISO8601Point.from_nonstandard_string(
                context_start_point)

        if context_end_point is None:
            self.context_end_point = None
        elif isinstance(context_end_point, ISO8601Point):
            self.context_end_point = context_end_point
        else:
            self.context_end_point = ISO8601Point.from_nonstandard_string(
                context_end_point)

        self.offset = ISO8601Interval.get_null()

        self._cached_first_point_values = {}
        self._cached_next_point_values = {}
        self._cached_valid_point_booleans = {}
        self._cached_recent_valid_points = []

        self.spec = dep_section
        self.abbrev_util = CylcTimeParser(self.context_start_point,
                                          self.context_end_point,
                                          WorkflowSpecifics.iso8601_parsers)
        # Parse_recurrence returns an isodatetime TimeRecurrence object
        # and a list of exclusion strings.
        self.recurrence, excl_points = self.abbrev_util.parse_recurrence(
            dep_section)

        # Determine the exclusion start point and end point
        try:
            exclusion_start_point = ISO8601Point.from_nonstandard_string(
                str(self.recurrence.start_point))
        except IsodatetimeError:
            exclusion_start_point = self.context_start_point

        try:
            exclusion_end_point = ISO8601Point.from_nonstandard_string(
                str(self.recurrence.end_point))
        except IsodatetimeError:
            exclusion_end_point = self.context_end_point

        self.exclusions = []

        # Creating an exclusions object instead
        if excl_points:
            with contextlib.suppress(AttributeError):
                self.exclusions = ISO8601Exclusions(
                    excl_points,
                    exclusion_start_point,
                    exclusion_end_point)

        self.step = ISO8601Interval(str(self.recurrence.duration))
        self.value = str(self.recurrence)
        # Concatenate the strings in exclusion list
        if self.exclusions:
            self.value += '!' + str(self.exclusions)

    def get_interval(self):
        """Return the interval between points in this sequence."""
        return self.step

    def get_offset(self):
        """Deprecated: return the offset used for this sequence."""
        return self.offset

    def set_offset(self, i_offset):
        """Deprecated: alter state to i_offset the entire sequence."""
        self.recurrence += interval_parse(str(i_offset))
        self._cached_first_point_values = {}
        self._cached_next_point_values = {}
        self._cached_valid_point_booleans = {}
        self._cached_recent_valid_points = []
        self.value = str(self.recurrence) + '!' + str(self.exclusions)
        if self.exclusions:
            self.value += '!' + str(self.exclusions)

    # lru_cache'd see __init__()
    def _is_on_sequence(self, point):
        """Return True if point is on-sequence."""
        # Iterate starting at recent valid points, for speed.
        if self.exclusions and point in self.exclusions:
            return False

        for valid_point in reversed(self._cached_recent_valid_points):
            if valid_point == point:
                return True
            if valid_point > point:
                continue
            next_point = valid_point
            while next_point is not None and next_point < point:
                next_point = self.get_next_point_on_sequence(next_point)
            if next_point is None:
                continue
            if next_point == point:
                return True
        return self.recurrence.get_is_valid(point_parse(point.value))

    def is_valid(self, point):
        """Return True if point is on-sequence and in-bounds."""
        try:
            return self._cached_valid_point_booleans[point.value]
        except KeyError:
            is_valid = self.is_on_sequence(point)
            if (len(self._cached_valid_point_booleans) >
                    self._MAX_CACHED_POINTS):
                self._cached_valid_point_booleans.popitem()
            self._cached_valid_point_booleans[point.value] = is_valid
            return is_valid

    def get_prev_point(self, point):
        """Return the previous point < point, or None if out of bounds."""
        # may be None if out of the recurrence bounds
        res = None
        prev_point = self.recurrence.get_prev(point_parse(point.value))
        if prev_point:
            res = ISO8601Point(str(prev_point))
            if res == point:
                raise SequenceDegenerateError(self.recurrence,
                                              WorkflowSpecifics.DUMP_FORMAT,
                                              res, point)
            # Check if res point is in the list of exclusions
            # If so, check the previous point by recursion.
            # Once you have found a point that is *not* in the exclusion
            # list, you can return it.
            if self.exclusions and res in self.exclusions:
                return self.get_prev_point(res)
        return res

    def get_nearest_prev_point(self, point):
        """Return the largest point < some arbitrary point."""
        if self.is_on_sequence(point):
            return self.get_prev_point(point)
        p_iso_point = point_parse(point.value)
        prev_cycle_point = None

        for recurrence_iso_point in self.recurrence:

            # Is recurrence point greater than arbitrary point?
            if recurrence_iso_point > p_iso_point:
                break
            recurrence_cycle_point = ISO8601Point(str(recurrence_iso_point))
            if self.exclusions and recurrence_cycle_point in self.exclusions:
                break
            prev_cycle_point = recurrence_cycle_point

        if prev_cycle_point is None:
            return None
        if prev_cycle_point == point:
            raise SequenceDegenerateError(
                self.recurrence, WorkflowSpecifics.DUMP_FORMAT,
                prev_cycle_point, point
            )
        # Check all exclusions
        if self.exclusions and prev_cycle_point in self.exclusions:
            return self.get_prev_point(prev_cycle_point)
        return prev_cycle_point

    def get_next_point(self, point):
        """Return the next point > p, or None if out of bounds."""
        with contextlib.suppress(KeyError):
            return ISO8601Point(self._cached_next_point_values[point.value])
        # Iterate starting at recent valid points, for speed.
        for valid_point in reversed(self._cached_recent_valid_points):
            if valid_point >= point:
                continue
            next_point = valid_point
            excluded = False
            while next_point is not None and (next_point <= point or excluded):
                excluded = False
                next_point = self.get_next_point_on_sequence(next_point)
                if next_point and next_point in self.exclusions:
                    excluded = True
            if next_point is not None:
                self._check_and_cache_next_point(point, next_point)
                return next_point
        # Iterate starting at the beginning.
        p_iso_point = point_parse(point.value)
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point > p_iso_point:
                next_point = ISO8601Point(str(recurrence_iso_point))
                if next_point and next_point in self.exclusions:
                    continue
                self._check_and_cache_next_point(point, next_point)
                return next_point
        return None

    def _check_and_cache_next_point(self, point, next_point):
        """Verify and cache the get_next_point return info."""
        # Verify next_point != point.
        if next_point == point:
            raise SequenceDegenerateError(
                self.recurrence, WorkflowSpecifics.DUMP_FORMAT,
                next_point, point
            )

        # Cache the answer for point -> next_point.
        if (len(self._cached_next_point_values) >
                self._MAX_CACHED_POINTS):
            self._cached_next_point_values.popitem()
        self._cached_next_point_values[point.value] = next_point.value

        # Cache next_point as a valid starting point for this recurrence.
        if (len(self._cached_next_point_values) >
                self._MAX_CACHED_POINTS):
            self._cached_recent_valid_points.pop(0)
        self._cached_recent_valid_points.append(next_point)

    def get_next_point_on_sequence(
        self, point: ISO8601Point
    ) -> Optional[ISO8601Point]:
        """Return the on-sequence point > point assuming that point is
        on-sequence, or None if out of bounds."""
        result = None
        next_point = self.recurrence.get_next(point_parse(point.value))
        if next_point:
            result = ISO8601Point(str(next_point))
            if result == point:
                raise SequenceDegenerateError(
                    self.recurrence, WorkflowSpecifics.DUMP_FORMAT,
                    point, result
                )
        # Check it is in the exclusions list now
        if result and result in self.exclusions:
            return self.get_next_point_on_sequence(result)
        return result

    def get_first_point(self, point):
        """Return the first point >= to point, or None if out of bounds."""
        with contextlib.suppress(KeyError):
            return ISO8601Point(self._cached_first_point_values[point.value])
        p_iso_point = point_parse(point.value)
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point >= p_iso_point:
                first_point_value = str(recurrence_iso_point)
                ret = ISO8601Point(first_point_value)
                # Check multiple exclusions
                if ret and ret in self.exclusions:
                    return self.get_next_point_on_sequence(ret)
                if (len(self._cached_first_point_values) >
                        self._MAX_CACHED_POINTS):
                    self._cached_first_point_values.popitem()
                self._cached_first_point_values[point.value] = (
                    first_point_value)
                return ret
        return None

    def get_start_point(self):
        """Return the first point in this sequence, or None."""
        for recurrence_iso_point in self.recurrence:
            point = ISO8601Point(str(recurrence_iso_point))
            # Check for multiple exclusions
            if not self.exclusions or point not in self.exclusions:
                return point
        return None

    def get_stop_point(self):
        """Return the last point in this sequence, or None if unbounded."""
        if (self.recurrence.repetitions is not None or (
                (self.recurrence.start_point is not None or
                 self.recurrence.min_point is not None) and
                (self.recurrence.end_point is not None or
                 self.recurrence.max_point is not None))):
            curr = None
            prev = None
            for recurrence_iso_point in self.recurrence:
                prev = curr
                curr = recurrence_iso_point
            ret = ISO8601Point(str(curr))
            if self.exclusions and ret in self.exclusions:
                return ISO8601Point(str(prev))
            return ret
        return None

    def __eq__(self, other):
        # Return True if other (sequence) is equal to self.
        if self.TYPE != other.TYPE:
            return False
        if self.value == other.value:
            return True
        return False

    def __lt__(self, other):
        return self.value < other.value

    def __str__(self):
        return self.value

    def __hash__(self) -> int:
        return hash(self.value)


def _get_old_anchor_step_recurrence(anchor, step, start_point):
    """Return a string representing an old-format recurrence translation."""
    anchor_point = ISO8601Point.from_nonstandard_string(anchor)
    # We may need to adjust the anchor downwards if it is ahead of the start.
    if start_point is not None:
        while anchor_point >= start_point + step:
            anchor_point -= step
    return str(anchor_point) + "/" + str(step)


def ingest_time(value: str, now: Optional[str] = None) -> str:
    """Handle relative, truncated and prev/next cycle points.

    Args:
        value: The string containing the previous()/next() stuff.
        now: A time point to use as the context for resolving the value.
    """
    # remove extraneous whitespace from cycle point
    value = value.replace(" ", "")
    parser = WorkflowSpecifics.point_parser

    # integer point or old-style date-time cycle point format
    is_integer = bool(re.match(r"\d+$", value))
    # iso8601 expanded year
    is_expanded = (
        (value.startswith("-") or value.startswith("+"))
        and "P" not in value
    )
    # previous() or next()
    is_prev_next = "next" in value or "previous" in value
    # offset from now (±P...)
    is_offset = value.startswith("P") or value.startswith("-P")

    if (
        is_integer
        or is_expanded
    ):
        # we don't need to do any fancy processing
        return value

    # parse the timepoint if needed
    if is_prev_next or is_offset:
        # `value` isn't necessarily valid ISO8601
        timepoint = None
        is_truncated = None
    else:
        timepoint = parser.parse(value)
        # missing date-time components off the front (e.g. 01T00)
        is_truncated = timepoint.truncated

    if not (is_prev_next or is_offset or is_truncated):
        return value

    if now is None:
        now = get_current_time_string()
    now_point = parser.parse(now)

    # correct for year in 'now' if year is the only date unit specified -
    # https://github.com/cylc/cylc-flow/issues/4805#issuecomment-1103928604
    if re.search(r"\(-\d{2}[);T]", value):
        now_point += Duration(years=1)
    # likewise correct for month if year and month are the only date units
    elif re.search(r"\(-\d{4}[);T]", value):
        now_point += Duration(months=1)

    # perform whatever transformation is required
    offset = None
    if is_prev_next:
        cycle_point, offset = prev_next(value, now_point, parser)
    elif is_offset:
        cycle_point = now_point
        offset = value
    else:  # is_truncated
        cycle_point = now_point + timepoint

    if offset is not None:
        # add/subtract offset duration to/from chosen timepoint
        duration_parser = WorkflowSpecifics.interval_parser
        offset = offset.replace('+', '')
        cycle_point += duration_parser.parse(offset)

    return str(cycle_point)


def prev_next(
    value: str, now: 'TimePoint', parser: 'TimePointParser'
) -> Tuple['TimePoint', Optional[str]]:
    """Handle previous() and next() syntax.

    Args:
        value: The string containing the previous()/next() stuff.
        now: A time point to use as the context for resolving the value.
        parser: A time point parser.

    Returns
        (cycle point, offset)
    """
    # are we in gregorian mode (or some other eccentric calendar
    if CALENDAR.mode != Calendar.MODE_GREGORIAN:
        raise CylcConfigError(
            'previous()/next() syntax must be used with integer or gregorian'
            f' cycling modes ("{value}")'
        )

    # break down cycle point into constituent parts.
    direction, tmp = value.split("(")
    offset: Optional[str]
    tmp, offset = tmp.split(")")

    offset = offset.strip() or None

    str_points: List[str] = tmp.split(";")
    timepoints: List['TimePoint'] = []

    # for use with 'previous' below.
    go_back = {
        "minute_of_hour": "PT1M",
        "hour_of_day": "PT1H",
        "day_of_week": "P1D",
        "day_of_month": "P1D",
        "day_of_year": "P1D",
        "week_of_year": "P1W",
        "month_of_year": "P1M",
        "year_of_decade": "P1Y",
        "decade_of_century": "P10Y",
        "year_of_century": "P1Y",
        "century": "P100Y"
    }

    for my_time in str_points:
        try:
            parsed_point = parser.parse(my_time.strip())
        except ValueError:
            suggest = my_time.replace(',', ';')
            raise WorkflowConfigError(
                f'Invalid offset: {my_time}:'
                f' Offset lists are semicolon separated, try {suggest}'
            )

        timepoints.append(parsed_point + now)

        if direction == 'previous':
            # for 'previous' determine next largest unit,
            # from go_back dict (defined outside 'for' loop), and
            # subtract 1 of it from each timepoint
            duration_parser = WorkflowSpecifics.interval_parser
            next_unit = parsed_point.get_smallest_missing_property_name()

            timepoints[-1] -= duration_parser.parse(go_back[next_unit])

    my_diff = [abs(my_time - now) for my_time in timepoints]

    cycle_point = timepoints[my_diff.index(min(my_diff))]

    # ensure truncated dates do not have time from 'now' included' -
    # https://github.com/metomi/isodatetime/issues/212
    if 'T' not in value.split(')')[0]:
        # NOTE: Strictly speaking we shouldn't forcefully mutate TimePoints
        # in this way as they're meant to be immutable since
        # https://github.com/metomi/isodatetime/pull/165, however it
        # should be ok as long as the TimePoint is not used as a dict key and
        # we don't call any of the TimePoint's cached methods until after we've
        # finished mutating it.
        cycle_point._hour_of_day = 0
        cycle_point._minute_of_hour = 0
        cycle_point._second_of_minute = 0
    # likewise ensure month and day from 'now' are not included
    # where they did not appear in the truncated datetime
    if re.search(r"\(-\d{2}[);T]", value):
        # case 1 - year only
        cycle_point._month_of_year = 1
        cycle_point._day_of_month = 1
    elif re.search(r"\(-(-\d{2}|\d{4})[;T)]", value):
        # case 2 - month only or year and month
        cycle_point._day_of_month = 1

    return cycle_point, offset


def init_from_cfg(cfg):
    """Initialise global variables (yuk) based on the configuration."""
    num_expanded_year_digits = cfg['scheduler'][
        'cycle point num expanded year digits']
    time_zone = cfg['scheduler']['cycle point time zone']
    custom_dump_format = cfg['scheduler']['cycle point format']
    assume_utc = cfg['scheduler']['UTC mode']
    cycling_mode = cfg['scheduling']['cycling mode']

    init(
        num_expanded_year_digits=num_expanded_year_digits,
        custom_dump_format=custom_dump_format,
        time_zone=time_zone,
        assume_utc=assume_utc,
        cycling_mode=cycling_mode
    )


def init(num_expanded_year_digits=0, custom_dump_format=None, time_zone=None,
         assume_utc=False, cycling_mode=None):
    """Initialise workflow-setup-specific information."""
    if cycling_mode in Calendar.default().MODES:
        Calendar.default().set_mode(cycling_mode)

    if time_zone is None:
        if assume_utc:
            time_zone = "Z"
            time_zone_hours_minutes = (0, 0)
        else:
            time_zone = get_local_time_zone_format(TimeZoneFormatMode.reduced)
            time_zone_hours_minutes = get_local_time_zone()
    else:
        time_zone_hours_minutes = TimePointDumper().get_time_zone(time_zone)
    WorkflowSpecifics.ASSUMED_TIME_ZONE = time_zone_hours_minutes
    WorkflowSpecifics.NUM_EXPANDED_YEAR_DIGITS = num_expanded_year_digits
    if custom_dump_format is None:
        if num_expanded_year_digits > 0:
            WorkflowSpecifics.DUMP_FORMAT = (
                EXPANDED_DATE_TIME_FORMAT + time_zone
            )
        else:
            WorkflowSpecifics.DUMP_FORMAT = DATE_TIME_FORMAT + time_zone
    else:
        WorkflowSpecifics.DUMP_FORMAT = custom_dump_format
        if "+X" not in custom_dump_format and num_expanded_year_digits:
            raise IllegalValueError(
                'cycle point format',
                ('cylc', 'cycle point format'),
                WorkflowSpecifics.DUMP_FORMAT
            )

    WorkflowSpecifics.iso8601_parsers = CylcTimeParser.initiate_parsers(
        dump_format=WorkflowSpecifics.DUMP_FORMAT,
        num_expanded_year_digits=num_expanded_year_digits,
        assumed_time_zone=WorkflowSpecifics.ASSUMED_TIME_ZONE
    )

    (WorkflowSpecifics.point_parser,
     WorkflowSpecifics.interval_parser,
     WorkflowSpecifics.recurrence_parser) = WorkflowSpecifics.iso8601_parsers

    WorkflowSpecifics.abbrev_util = CylcTimeParser(
        None, None, WorkflowSpecifics.iso8601_parsers
    )


def get_dump_format():
    """Return cycle point string dump format."""
    return WorkflowSpecifics.DUMP_FORMAT


def get_point_relative(offset_string, base_point):
    """Create a point from offset_string applied to base_point."""
    try:
        interval = ISO8601Interval(str(interval_parse(offset_string)))
    except IsodatetimeError:
        return ISO8601Point(str(
            WorkflowSpecifics.abbrev_util.parse_timepoint(
                offset_string, context_point=point_parse(base_point.value))
        ))
    else:
        return base_point + interval


def interval_parse(interval_string):
    """Parse an interval_string into a proper Duration class."""
    try:
        return _interval_parse(interval_string)
    except Exception:
        try:
            return -1 * _interval_parse(interval_string.replace("-", "", 1))
        except Exception:
            return _interval_parse(interval_string.replace("+", "", 1))


def is_offset_absolute(offset_string):
    """Return True if offset_string is a point rather than an interval."""
    try:
        interval_parse(offset_string)
    except Exception:
        return True
    else:
        return False


@lru_cache(10000)
def _interval_parse(interval_string):
    """Parse an interval_string into a proper Duration object."""
    return WorkflowSpecifics.interval_parser.parse(interval_string)


def point_parse(point_string: str) -> 'TimePoint':
    """Parse a point_string into a proper TimePoint object."""
    return _point_parse(point_string, WorkflowSpecifics.DUMP_FORMAT)


@lru_cache(10000)
def _point_parse(point_string, _dump_fmt):
    """Parse a point_string into a proper TimePoint object."""
    if "%" in WorkflowSpecifics.DUMP_FORMAT:
        # May be a custom not-quite ISO 8601 dump format.
        with contextlib.suppress(IsodatetimeError):
            return WorkflowSpecifics.point_parser.strptime(
                point_string, WorkflowSpecifics.DUMP_FORMAT)
    # Attempt to parse it in ISO 8601 format.
    return WorkflowSpecifics.point_parser.parse(point_string)
