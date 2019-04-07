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

"""Date-time cycling by point, interval, and sequence classes."""

import re

from isodatetime.data import Calendar, Duration
from isodatetime.dumpers import TimePointDumper
from isodatetime.timezone import (
    get_local_time_zone, get_local_time_zone_format, TimeZoneFormatMode)
from cylc.time_parser import CylcTimeParser
from cylc.cycling import (
    PointBase, IntervalBase, SequenceBase, ExclusionBase, cmp_to_rich, cmp
)
from cylc.exceptions import (
    SequenceDegenerateError, PointParsingError, IntervalParsingError
)
from cylc.wallclock import get_current_time_string
from parsec.validate import IllegalValueError

CYCLER_TYPE_ISO8601 = "iso8601"
CYCLER_TYPE_SORT_KEY_ISO8601 = "b"

MEMOIZE_LIMIT = 10000

DATE_TIME_FORMAT = "CCYYMMDDThhmm"
EXPANDED_DATE_TIME_FORMAT = "+XCCYYMMDDThhmm"
NEW_DATE_TIME_REC = re.compile("T")

WARNING_PARSE_EXPANDED_YEAR_DIGITS = (
    "(incompatible with [cylc]cycle point num expanded year digits = %s ?)")


class SuiteSpecifics(object):

    """Store suite-setup-specific constants and utilities here."""
    ASSUMED_TIME_ZONE = None
    DUMP_FORMAT = None
    NUM_EXPANDED_YEAR_DIGITS = None
    abbrev_util = None
    interval_parser = None
    point_parser = None
    recurrence_parser = None
    iso8601_parsers = None


def memoize(function):
    """This stores results for a given set of inputs to a function.

    The inputs and results of the function must be immutable.
    Keyword arguments are not allowed.

    To avoid memory leaks, only the first 10000 separate input
    permutations are cached for a given function.

    """
    inputs_results = {}

    def _wrapper(*args):
        """Cache results for function(*args)."""
        try:
            return inputs_results[args]
        except KeyError:
            results = function(*args)
            if len(inputs_results) > MEMOIZE_LIMIT:
                # Full up, no more room.
                inputs_results.popitem()
            inputs_results[args] = results
            return results
    return _wrapper


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

    def __cmp__(self, other):
        # Compare other (point) to self.
        if other is None:
            return -1
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self._iso_point_cmp(self.value, other.value)

    def standardise(self):
        """Reformat self.value into a standard representation."""
        try:
            self.value = str(point_parse(self.value))
        except ValueError as exc:
            if self.value.startswith("+") or self.value.startswith("-"):
                message = WARNING_PARSE_EXPANDED_YEAR_DIGITS % (
                    SuiteSpecifics.NUM_EXPANDED_YEAR_DIGITS)
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

    def __hash__(self):
        return hash(self.value)

    @staticmethod
    @memoize
    def _iso_point_add(point_string, interval_string):
        """Add the parsed point_string to the parsed interval_string."""
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point + interval)

    @staticmethod
    @memoize
    def _iso_point_cmp(point_string, other_point_string):
        """Compare the parsed point_string to the other one."""
        point = point_parse(point_string)
        other_point = point_parse(other_point_string)
        return cmp(point, other_point)

    @staticmethod
    @memoize
    def _iso_point_sub_interval(point_string, interval_string):
        """Return the parsed point_string minus the parsed interval_string."""
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point - interval)

    @staticmethod
    @memoize
    def _iso_point_sub_point(point_string, other_point_string):
        """Return the difference between the two parsed point strings."""
        point = point_parse(point_string)
        other_point = point_parse(other_point_string)
        return str(point - other_point)


# TODO: replace __cmp__ infrastructure
cmp_to_rich(ISO8601Point)


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

    def get_inferred_child(self, string):
        """Return an instance with 'string' amounts of my non-zero units."""
        interval = interval_parse(self.value)
        amount_per_unit = int(string)
        unit_amounts = {}
        for attribute in ["years", "months", "weeks", "days",
                          "hours", "minutes", "seconds"]:
            if getattr(interval, attribute):
                unit_amounts[attribute] = amount_per_unit
        interval = Duration(**unit_amounts)
        return ISO8601Interval(str(interval))

    def standardise(self):
        """Format self.value into a standard representation."""
        try:
            self.value = str(interval_parse(self.value))
        except ValueError:
            raise IntervalParsingError(type(self), self.value)
        return self

    def add(self, other):
        """Add other to self (point or interval) c.f. ISO 8601."""
        if isinstance(other, ISO8601Interval):
            return ISO8601Interval(
                self._iso_interval_add(self.value, other.value))
        return other + self

    def cmp_(self, other):
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
    @memoize
    def _iso_interval_abs(interval_string, other_interval_string):
        """Return the absolute (non-negative) value of an interval_string."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        if interval < other:
            return str(interval * -1)
        return interval_string

    @staticmethod
    @memoize
    def _iso_interval_add(interval_string, other_interval_string):
        """Return one parsed interval_string plus the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval + other)

    @staticmethod
    @memoize
    def _iso_interval_cmp(interval_string, other_interval_string):
        """Compare one parsed interval_string with the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return cmp(interval, other)

    @staticmethod
    @memoize
    def _iso_interval_sub(interval_string, other_interval_string):
        """Subtract one parsed interval_string from the other one."""
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval - other)

    @staticmethod
    @memoize
    def _iso_interval_mul(interval_string, factor):
        """Multiply one parsed interval_string's values by factor."""
        interval = interval_parse(interval_string)
        return str(interval * factor)

    @staticmethod
    @memoize
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
                 'recurrence', 'exclusions', 'step', 'value')

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

        if context_start_point is None:
            self.context_start_point = context_start_point
        elif isinstance(context_start_point, ISO8601Point):
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
                                          SuiteSpecifics.iso8601_parsers)
        # Parse_recurrence returns an isodatetime TimeRecurrence object
        # and a list of exclusion strings.
        self.recurrence, excl_points = self.abbrev_util.parse_recurrence(
            dep_section)

        # Determine the exclusion start point and end point
        try:
            exclusion_start_point = ISO8601Point.from_nonstandard_string(
                str(self.recurrence.start_point))
        except ValueError:
            exclusion_start_point = self.context_start_point

        try:
            exclusion_end_point = ISO8601Point.from_nonstandard_string(
                str(self.recurrence.end_point))
        except ValueError:
            exclusion_end_point = self.context_end_point

        self.exclusions = []

        # Creating an exclusions object instead
        if excl_points:
            try:
                self.exclusions = ISO8601Exclusions(
                    excl_points,
                    exclusion_start_point,
                    exclusion_end_point)
            except AttributeError:
                pass

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
        if self.recurrence.start_point is not None:
            self.recurrence.start_point += interval_parse(str(i_offset))
        if self.recurrence.end_point is not None:
            self.recurrence.end_point += interval_parse(str(i_offset))
        self._cached_first_point_values = {}
        self._cached_next_point_values = {}
        self._cached_valid_point_booleans = {}
        self._cached_recent_valid_points = []
        self.value = str(self.recurrence) + '!' + str(self.exclusions)
        if self.exclusions:
            self.value += '!' + str(self.exclusions)

    def is_on_sequence(self, point):
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
                                              SuiteSpecifics.DUMP_FORMAT,
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
                self.recurrence, SuiteSpecifics.DUMP_FORMAT,
                prev_cycle_point, point
            )
        # Check all exclusions
        if self.exclusions and prev_cycle_point in self.exclusions:
            return self.get_prev_point(prev_cycle_point)
        return prev_cycle_point

    def get_next_point(self, point):
        """Return the next point > p, or None if out of bounds."""
        try:
            return ISO8601Point(self._cached_next_point_values[point.value])
        except KeyError:
            pass
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
                self.recurrence, SuiteSpecifics.DUMP_FORMAT,
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

    def get_next_point_on_sequence(self, point):
        """Return the on-sequence point > point assuming that point is
        on-sequence, or None if out of bounds."""
        result = None
        next_point = self.recurrence.get_next(point_parse(point.value))
        if next_point:
            result = ISO8601Point(str(next_point))
            if result == point:
                raise SequenceDegenerateError(
                    self.recurrence, SuiteSpecifics.DUMP_FORMAT,
                    point, result
                )
        # Check it is in the exclusions list now
        if result and result in self.exclusions:
            return self.get_next_point_on_sequence(result)
        return result

    def get_first_point(self, point):
        """Return the first point >= to point, or None if out of bounds."""
        try:
            return ISO8601Point(self._cached_first_point_values[point.value])
        except KeyError:
            pass
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

    def __hash__(self):
        return hash(self.value)


def _get_old_anchor_step_recurrence(anchor, step, start_point):
    """Return a string representing an old-format recurrence translation."""
    anchor_point = ISO8601Point.from_nonstandard_string(anchor)
    # We may need to adjust the anchor downwards if it is ahead of the start.
    if start_point is not None:
        while anchor_point >= start_point + step:
            anchor_point -= step
    return str(anchor_point) + "/" + str(step)


def ingest_time(value, my_now=None):
    """
    Allows for relative and truncated cycle points,
    and cycle point as an offset from 'now'
    """

    # Send back integer cycling, date-only, and expanded datetimes.
    if re.match(r"\d+$", value):
        # Could be an old date-time cycle point format, or integer format.
        return value
    if (value.startswith("-") or value.startswith("+")) and "P" not in value:
        # Expanded year
        return value

    parser = SuiteSpecifics.point_parser
    offset = None

    if my_now is None:
        my_now = parser.parse(get_current_time_string())
    else:
        my_now = parser.parse(my_now)

    # remove extraneous whitespace from cycle point
    value = value.replace(" ", "")

    # correct for year in 'now' if year only,
    # or year and time, specified in input
    if re.search(r"\(-\d{2}[);T]", value):
        my_now.year = my_now.year + 1

    # correct for month in 'now' if year and month only,
    # or year, month and time, specified in input
    elif re.search(r"\(-\d{4}[);T]", value):
        my_now.month_of_year = my_now.month_of_year + 1

    if "next" in value or "previous" in value:

        # break down cycle point into constituent parts.
        direction, tmp = value.split("(")
        tmp, offset = tmp.split(")")

        if offset.strip() == '':
            offset = None
        else:
            offset = offset.strip()

        timepoints = tmp.split(";")

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
            "century": "P100Y"}

        for i_time, my_time in enumerate(timepoints):
            parsed_point = parser.parse(my_time.strip())
            timepoints[i_time] = parsed_point + my_now

            if direction == 'previous':
                # for 'previous' determine next largest unit,
                # from go_back dict (defined outside 'for' loop), and
                # subtract 1 of it from each timepoint
                duration_parser = SuiteSpecifics.interval_parser
                next_unit = parsed_point.get_smallest_missing_property_name()

                timepoints[i_time] = (
                    timepoints[i_time] -
                    duration_parser.parse(go_back[next_unit]))

        my_diff = []
        my_diff = [abs(my_time - my_now) for my_time in timepoints]

        my_cp = timepoints[my_diff.index(min(my_diff))]

        # ensure truncated dates do not have
        # time from 'now' included'
        if 'T' not in value.split(')')[0]:
            my_cp.hour_of_day = 0
            my_cp.minute_of_hour = 0
            my_cp.second_of_minute = 0
        # ensure month and day from 'now' are not included
        # where they did not appear in the truncated datetime
        # NOTE: this may break when the order of tick over
        # for time point is reversed!!!
        # https://github.com/metomi/isodatetime/pull/101
        # case 1 - year only
        if re.search(r"\(-\d{2}[);T]", value):
            my_cp.month_of_year = 1
            my_cp.day_of_month = 1
        # case 2 - month only or year and month
        elif re.search(r"\(-(-\d{2}|\d{4})[;T)]", value):
            my_cp.day_of_month = 1

    elif value.startswith("P") or value.startswith("-P"):
        my_cp = my_now
        offset = value

    else:
        timepoint = parser.parse(value)
        if timepoint.truncated is False:
            return value
        my_cp = my_now + timepoint

    if offset is not None:
        # add/subtract offset duration to/from chosen timepoint
        duration_parser = SuiteSpecifics.interval_parser

        offset = offset.replace('+', '')
        offset = duration_parser.parse(offset)
        my_cp = my_cp + offset

    return str(my_cp)


def init_from_cfg(cfg):
    """Initialise global variables (yuk) based on the configuration."""
    num_expanded_year_digits = cfg['cylc'][
        'cycle point num expanded year digits']
    time_zone = cfg['cylc']['cycle point time zone']
    custom_dump_format = cfg['cylc']['cycle point format']
    assume_utc = cfg['cylc']['UTC mode']
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
    """Initialise suite-setup-specific information."""
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
    SuiteSpecifics.ASSUMED_TIME_ZONE = time_zone_hours_minutes
    SuiteSpecifics.NUM_EXPANDED_YEAR_DIGITS = num_expanded_year_digits
    if custom_dump_format is None:
        if num_expanded_year_digits > 0:
            SuiteSpecifics.DUMP_FORMAT = EXPANDED_DATE_TIME_FORMAT + time_zone
        else:
            SuiteSpecifics.DUMP_FORMAT = DATE_TIME_FORMAT + time_zone
    else:
        SuiteSpecifics.DUMP_FORMAT = custom_dump_format
        if "+X" not in custom_dump_format and num_expanded_year_digits:
            raise IllegalValueError(
                'cycle point format',
                ('cylc', 'cycle point format'),
                SuiteSpecifics.DUMP_FORMAT
            )

    SuiteSpecifics.iso8601_parsers = CylcTimeParser.initiate_parsers(
        dump_format=SuiteSpecifics.DUMP_FORMAT,
        num_expanded_year_digits=num_expanded_year_digits,
        assumed_time_zone=SuiteSpecifics.ASSUMED_TIME_ZONE
    )

    (SuiteSpecifics.point_parser,
     SuiteSpecifics.interval_parser,
     SuiteSpecifics.recurrence_parser) = SuiteSpecifics.iso8601_parsers

    SuiteSpecifics.abbrev_util = CylcTimeParser(
        None, None, SuiteSpecifics.iso8601_parsers
    )


def get_point_relative(offset_string, base_point):
    """Create a point from offset_string applied to base_point."""
    try:
        interval = ISO8601Interval(str(interval_parse(offset_string)))
    except ValueError:
        return ISO8601Point(str(
            SuiteSpecifics.abbrev_util.parse_timepoint(
                offset_string, context_point=_point_parse(base_point.value))
        ))
    else:
        return base_point + interval


def interval_parse(interval_string):
    """Parse an interval_string into a proper Duration class."""
    try:
        return _interval_parse(interval_string).copy()
    except Exception:
        try:
            return -1 * _interval_parse(
                interval_string.replace("-", "", 1)).copy()
        except Exception:
            return _interval_parse(
                interval_string.replace("+", "", 1)).copy()


def is_offset_absolute(offset_string):
    """Return True if offset_string is a point rather than an interval."""
    try:
        interval_parse(offset_string)
    except Exception:
        return True
    else:
        return False


@memoize
def _interval_parse(interval_string):
    """Parse an interval_string into a proper Duration object."""
    return SuiteSpecifics.interval_parser.parse(interval_string)


def point_parse(point_string):
    """Parse a point_string into a proper TimePoint object."""
    return _point_parse(point_string).copy()


@memoize
def _point_parse(point_string):
    """Parse a point_string into a proper TimePoint object."""
    if "%" in SuiteSpecifics.DUMP_FORMAT:
        # May be a custom not-quite ISO 8601 dump format.
        try:
            return SuiteSpecifics.point_parser.strptime(
                point_string, SuiteSpecifics.DUMP_FORMAT)
        except ValueError:
            pass
    # Attempt to parse it in ISO 8601 format.
    return SuiteSpecifics.point_parser.parse(point_string)
