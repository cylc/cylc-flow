# -*- coding: utf-8 -*-

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
import unittest

from isodatetime.data import Calendar, Duration
from isodatetime.dumpers import TimePointDumper
from isodatetime.parsers import TimePointParser, DurationParser
from isodatetime.timezone import (
    get_local_time_zone, get_local_time_zone_format)
from cylc.time_parser import CylcTimeParser
from cylc.cycling import (
    PointBase, IntervalBase, SequenceBase, ExclusionBase, PointParsingError,
    IntervalParsingError, SequenceDegenerateError)
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

    def __nonzero__(self):
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

    __slots__ = ExclusionBase.__slots__ + ('p_iso_exclusions',)

    def __init__(self, excl_points, start_point, end_point=None):
        super(ISO8601Exclusions, self).__init__(start_point, end_point)
        self.p_iso_exclusions = []
        self.build_exclusions(excl_points)

    def build_exclusions(self, excl_points):
        for point in excl_points:
            try:
                # Try making an ISO8601Point
                exclusion_point = ISO8601Point.from_nonstandard_string(
                    str(point)) if point else None
                if exclusion_point not in self.exclusion_points:
                    self.exclusion_points.append(exclusion_point)
                    self.p_iso_exclusions.append(str(exclusion_point))
            except (AttributeError, TypeError, ValueError):
                # Try making an ISO8601Sequence
                exclusion = ISO8601Sequence(point, self.exclusion_start_point,
                                            self.exclusion_end_point)
                self.exclusion_sequences.append(exclusion)


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

    def set_offset(self, offset):
        """Deprecated: alter state to offset the entire sequence."""
        if self.recurrence.start_point is not None:
            self.recurrence.start_point += interval_parse(str(offset))
        if self.recurrence.end_point is not None:
            self.recurrence.end_point += interval_parse(str(offset))
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
        prev_iso_point = None

        for recurrence_iso_point in self.recurrence:
            # Is recurrence point greater than aribitrary point?
            if (
                    recurrence_iso_point > p_iso_point or
                    (self.exclusions and
                     recurrence_iso_point in self.exclusions.p_iso_exclusions)
            ):
                break
            prev_iso_point = recurrence_iso_point
        if prev_iso_point is None:
            return None
        nearest_point = ISO8601Point(str(prev_iso_point))
        if nearest_point == point:
            raise SequenceDegenerateError(
                self.recurrence, SuiteSpecifics.DUMP_FORMAT,
                nearest_point, point
            )
        # Check all exclusions
        if self.exclusions and nearest_point in self.exclusions:
            return self.get_prev_point(nearest_point)
        return nearest_point

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

    def __str__(self):
        return self.value


def _get_old_anchor_step_recurrence(anchor, step, start_point):
    """Return a string representing an old-format recurrence translation."""
    anchor_point = ISO8601Point.from_nonstandard_string(anchor)
    # We may need to adjust the anchor downwards if it is ahead of the start.
    if start_point is not None:
        while anchor_point >= start_point + step:
            anchor_point -= step
    return str(anchor_point) + "/" + str(step)


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

    SuiteSpecifics.interval_parser = DurationParser()

    if cycling_mode in Calendar.default().MODES:
        Calendar.default().set_mode(cycling_mode)

    if time_zone is None:
        if assume_utc:
            time_zone = "Z"
            time_zone_hours_minutes = (0, 0)
        else:
            time_zone = get_local_time_zone_format(reduced_mode=True)
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
        if u"+X" not in custom_dump_format and num_expanded_year_digits:
            raise IllegalValueError(
                'cycle point format',
                ('cylc', 'cycle point format'),
                SuiteSpecifics.DUMP_FORMAT
            )
    SuiteSpecifics.point_parser = TimePointParser(
        allow_only_basic=False,
        allow_truncated=True,
        num_expanded_year_digits=SuiteSpecifics.NUM_EXPANDED_YEAR_DIGITS,
        dump_format=SuiteSpecifics.DUMP_FORMAT,
        assumed_time_zone=time_zone_hours_minutes
    )

    SuiteSpecifics.iso8601_parsers = CylcTimeParser.initiate_parsers(
        dump_format=SuiteSpecifics.DUMP_FORMAT,
        num_expanded_year_digits=num_expanded_year_digits,
        assumed_time_zone=SuiteSpecifics.ASSUMED_TIME_ZONE
    )

    SuiteSpecifics.abbrev_util = CylcTimeParser(
        None, None, SuiteSpecifics.iso8601_parsers
    )


def get_point_relative(offset_string, base_point):
    """Create a point from offset_string applied to base_point."""
    try:
        interval = ISO8601Interval(
            str(interval_parse(offset_string)))
    except Exception:
        pass
    else:
        return base_point + interval
    return ISO8601Point(str(
        SuiteSpecifics.abbrev_util.parse_timepoint(
            offset_string, context_point=_point_parse(base_point.value))
    ))


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


class TestISO8601Sequence(unittest.TestCase):
    """Contains unit tests for the ISO8601Sequence class."""

    def test_exclusions_simple(self):
        """Test the generation of points for sequences with exclusions."""
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!20000101T02Z', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        self.assertEqual(output, ['20000101T0000Z', '20000101T0100Z',
                                  '20000101T0300Z', '20000101T0400Z'])

    def test_exclusions_offset(self):
        """Test the generation of points for sequences with exclusions
        that have an offset on the end"""
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!20000101T00Z+PT1H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        self.assertEqual(output, ['20000101T0000Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z'])

    def test_multiple_exclusions_complex1(self):
        """Tests sequences that have multiple exclusions and a more
        complicated format"""

        # A sequence that specifies a dep start time
        sequence = ISO8601Sequence('20000101T01Z/PT1H!20000101T02Z',
                                   '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect one of the hours to be excluded: T02
        self.assertEqual(output, ['20000101T0100Z', '20000101T0300Z',
                                  '20000101T0400Z', '20000101T0500Z'])

    def test_multiple_exclusions_complex2(self):
        """Tests sequences that have multiple exclusions and a more
        complicated format"""

        # A sequence that specifies a dep start time
        sequence = ISO8601Sequence('20000101T01Z/PT1H!'
                                   '(20000101T02Z,20000101T03Z)',
                                   '20000101T00Z',
                                   '20000101T05Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 3:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect two of the hours to be excluded: T02, T03
        self.assertEqual(output, ['20000101T0100Z', '20000101T0400Z',
                                  '20000101T0500Z'])

    def test_multiple_exclusions_simple(self):
        """Tests generation of points for sequences with multiple exclusions
        """
        init(time_zone='Z')
        sequence = ISO8601Sequence('PT1H!(20000101T02Z,20000101T03Z)',
                                   '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make four sequence points
        while point and count < 4:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect two of the hours to be excluded: T02 and T03
        self.assertEqual(output, ['20000101T0000Z', '20000101T0100Z',
                                  '20000101T0400Z', '20000101T0500Z'])

    def test_advanced_exclusions_partial_datetime1(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run 3-hourly but not at 06:00 (from the ICP)
        sequence = ISO8601Sequence('PT3H!T06', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make ten sequence points
        while point and count < 10:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect every T06 to be excluded
        self.assertEqual(output, ['20000101T0000Z', '20000101T0300Z',
                                  '20000101T0900Z', '20000101T1200Z',
                                  '20000101T1500Z', '20000101T1800Z',
                                  '20000101T2100Z', '20000102T0000Z',
                                  '20000102T0300Z', '20000102T0900Z'])

    def test_advanced_exclusions_partial_datetime2(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly but not at 00:00, 06:00, 12:00, 18:00
        sequence = ISO8601Sequence('T-00!(T00, T06, T12, T18)', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 18 sequence points
        while point and count < 18:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect T00, T06, T12, and T18 to be excluded
        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z',
                                  '20000101T0500Z', '20000101T0700Z',
                                  '20000101T0800Z', '20000101T0900Z',
                                  '20000101T1000Z', '20000101T1100Z',
                                  '20000101T1300Z', '20000101T1400Z',
                                  '20000101T1500Z', '20000101T1600Z',
                                  '20000101T1700Z', '20000101T1900Z',
                                  '20000101T2000Z', '20000101T2100Z'])

    def test_advanced_exclusions_partial_datetime3(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run 5 minutely but not at 15 minutes past the hour from ICP
        sequence = ISO8601Sequence('PT5M!T-15', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 15 sequence points
        while point and count < 15:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect xx:15 (15 minutes past the hour) to be excluded
        self.assertEqual(output, ['20000101T0000Z', '20000101T0005Z',
                                  '20000101T0010Z',
                                  '20000101T0020Z', '20000101T0025Z',
                                  '20000101T0030Z', '20000101T0035Z',
                                  '20000101T0040Z', '20000101T0045Z',
                                  '20000101T0050Z', '20000101T0055Z',
                                  '20000101T0100Z', '20000101T0105Z',
                                  '20000101T0110Z', '20000101T0120Z'])

    def test_advanced_exclusions_partial_datetime4(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run daily at 00:00 except on Mondays
        sequence = ISO8601Sequence('T00!W-1T00', '20170422T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make 19 sequence points
        while point and count < 9:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect Monday 24th April and Monday 1st May
        # to be excluded.
        self.assertEqual(output, ['20170422T0000Z', '20170423T0000Z',
                                  '20170425T0000Z', '20170426T0000Z',
                                  '20170427T0000Z', '20170428T0000Z',
                                  '20170429T0000Z', '20170430T0000Z',
                                  '20170502T0000Z'])

    def test_exclusions_to_string(self):
        init(time_zone='Z')
        # Chack that exclusions are not included where they should not be.
        basic = ISO8601Sequence('PT1H', '2000', '2001')
        self.assertFalse('!' in str(basic))

        # Check that exclusions are parsable.
        sequence = ISO8601Sequence('PT1H!(20000101T10Z, PT6H)', '2000', '2001')
        sequence2 = ISO8601Sequence(str(sequence), '2000', '2001')
        self.assertEqual(sequence, sequence2)

    def test_advanced_exclusions_sequences1(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly from the ICP but not 3-hourly
        sequence = ISO8601Sequence('PT1H!PT3H', '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]
        # We should expect to see hourly from ICP but not 3 hourly
        self.assertEqual(output, ['20000101T0200Z', '20000101T0300Z',
                                  '20000101T0500Z', '20000101T0600Z',
                                  '20000101T0800Z', '20000101T0900Z'])

    def test_advanced_exclusions_sequences2(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run hourly on the hour but not 3 hourly on the hour
        sequence = ISO8601Sequence('T-00!T-00/PT3H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0400Z', '20000101T0500Z',
                                  '20000101T0700Z', '20000101T0800Z'])

    def test_advanced_exclusions_sequences3(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run daily at 12:00 except every 3rd day
        sequence = ISO8601Sequence('T12!P3D', '20000101T12Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000102T1200Z', '20000103T1200Z',
                                  '20000105T1200Z', '20000106T1200Z',
                                  '20000108T1200Z', '20000109T1200Z'])

    def test_advanced_exclusions_sequences4(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T01/PT1H!+PT3H/PT3H', '20000101T01Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0500Z',
                                  '20000101T0600Z', '20000101T0800Z'])

    def test_advanced_exclusions_sequences5(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T-00 ! 2000', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0200Z',
                                  '20000101T0300Z', '20000101T0400Z',
                                  '20000101T0500Z', '20000101T0600Z'])

    def test_advanced_exclusions_sequences_mix_points_sequences(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T-00 ! (2000, PT2H)', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0100Z', '20000101T0300Z',
                                  '20000101T0500Z', '20000101T0700Z',
                                  '20000101T0900Z', '20000101T1100Z'])

    def test_advanced_exclusions_sequences_implied_start_point(self):
        """Advanced exclusions refers to exclusions that are not just
        simple points but could be time periods or recurrences such as
        '!T06' or similar"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour.
        sequence = ISO8601Sequence('T05/PT1H!PT3H', '20000101T00Z')

        output = []
        point = sequence.get_start_point()
        count = 0
        # We are going to make six sequence points
        while point and count < 6:
            output.append(point)
            point = sequence.get_next_point(point)
            count += 1
        output = [str(out) for out in output]

        self.assertEqual(output, ['20000101T0600Z', '20000101T0700Z',
                                  '20000101T0900Z', '20000101T1000Z',
                                  '20000101T1200Z', '20000101T1300Z'])

    def test_exclusions_sequences_points(self):
        """Test ISO8601Sequence methods for sequences with exclusions"""
        init(time_zone='Z')
        # Run every hour from 01:00 excluding every 3rd hour
        sequence = ISO8601Sequence('T01/PT1H!PT3H', '20000101T01Z')

        point_0 = ISO8601Point('20000101T00Z')
        point_1 = ISO8601Point('20000101T01Z')
        point_2 = ISO8601Point('20000101T02Z')
        point_3 = ISO8601Point('20000101T03Z')
        point_4 = ISO8601Point('20000101T04Z')

        self.assertFalse(point_0 in sequence.exclusions)
        self.assertTrue(point_1 in sequence.exclusions)
        self.assertTrue(sequence.is_on_sequence(point_2))
        self.assertTrue(sequence.is_on_sequence(point_3))
        self.assertFalse(sequence.is_on_sequence(point_4))
        self.assertTrue(point_4 in sequence.exclusions)

    def test_exclusions_extensive(self):
        """Test ISO8601Sequence methods for sequences with exclusions"""
        init(time_zone='+05')
        sequence = ISO8601Sequence('PT1H!20000101T02+05', '20000101T00',
                                   '20000101T05')

        point_0 = ISO8601Point('20000101T0000+05')
        point_1 = ISO8601Point('20000101T0100+05')
        point_2 = ISO8601Point('20000101T0200+05')  # The excluded point.
        point_3 = ISO8601Point('20000101T0300+05')

        self.assertFalse(sequence.is_on_sequence(point_2))
        self.assertFalse(sequence.is_valid(point_2))
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_nearest_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_next_point(point_1), point_3)
        self.assertEqual(sequence.get_next_point(point_2), point_3)

        sequence = ISO8601Sequence('PT1H!20000101T00+05', '20000101T00+05')
        self.assertEqual(sequence.get_first_point(point_0), point_1)
        self.assertEqual(sequence.get_start_point(), point_1)

    def test_multiple_exclusions_extensive(self):
        """Test ISO8601Sequence methods for sequences with multiple exclusions
        """
        init(time_zone='+05')
        sequence = ISO8601Sequence('PT1H!(20000101T02,20000101T03)',
                                   '20000101T00',
                                   '20000101T06')

        point_0 = ISO8601Point('20000101T0000+05')
        point_1 = ISO8601Point('20000101T0100+05')
        point_2 = ISO8601Point('20000101T0200+05')  # First excluded point
        point_3 = ISO8601Point('20000101T0300+05')  # Second excluded point
        point_4 = ISO8601Point('20000101T0400+05')

        # Check the excluded points are not on the sequence
        self.assertFalse(sequence.is_on_sequence(point_2))
        self.assertFalse(sequence.is_on_sequence(point_3))
        self.assertFalse(sequence.is_valid(point_2))  # Should be excluded
        self.assertFalse(sequence.is_valid(point_3))  # Should be excluded
        # Check that we can correctly retrieve previous points
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        # Should skip two excluded points
        self.assertEqual(sequence.get_prev_point(point_4), point_1)
        self.assertEqual(sequence.get_prev_point(point_2), point_1)
        self.assertEqual(sequence.get_nearest_prev_point(point_4), point_1)
        self.assertEqual(sequence.get_next_point(point_1), point_4)
        self.assertEqual(sequence.get_next_point(point_3), point_4)

        sequence = ISO8601Sequence('PT1H!20000101T00+05', '20000101T00')
        # Check that the first point is after 00.
        self.assertEqual(sequence.get_first_point(point_0), point_1)
        self.assertEqual(sequence.get_start_point(), point_1)

        # Check a longer list of exclusions
        # Also note you can change the format of the exclusion list
        # (removing the parentheses)
        sequence = ISO8601Sequence('PT1H!(20000101T02+05, 20000101T03+05,'
                                   '20000101T04+05)',
                                   '20000101T00',
                                   '20000101T06')
        self.assertEqual(sequence.get_prev_point(point_3), point_1)
        self.assertEqual(sequence.get_prev_point(point_4), point_1)

    def test_simple(self):
        """Run some simple tests for date-time cycling."""
        init(time_zone='Z')
        p_start = ISO8601Point('20100808T00')
        p_stop = ISO8601Point('20100808T02')
        i = ISO8601Interval('PT6H')
        self.assertEqual(p_start - i, ISO8601Point('20100807T18'))
        self.assertEqual(p_stop + i, ISO8601Point('20100808T08'))

        sequence = ISO8601Sequence('PT10M', str(p_start), str(p_stop),)
        sequence.set_offset(- ISO8601Interval('PT10M'))
        point = sequence.get_next_point(ISO8601Point('20100808T0000'))
        self.assertEqual(point, ISO8601Point('20100808T0010'))
        output = []

        # Test point generation forwards.
        while point and point < p_stop:
            output.append(point)
            self.assertTrue(sequence.is_on_sequence(point))
            point = sequence.get_next_point(point)
        self.assertEqual([str(out) for out in output],
                         ['20100808T0010Z', '20100808T0020Z',
                          '20100808T0030Z', '20100808T0040Z',
                          '20100808T0050Z', '20100808T0100Z',
                          '20100808T0110Z', '20100808T0120Z',
                          '20100808T0130Z', '20100808T0140Z',
                          '20100808T0150Z'])

        self.assertEqual(point, ISO8601Point('20100808T0200'))

        # Test point generation backwards.
        output = []
        while point and point >= p_start:
            output.append(point)
            self.assertTrue(sequence.is_on_sequence(point))
            point = sequence.get_prev_point(point)
        self.assertEqual([str(out) for out in output],
                         ['20100808T0200Z', '20100808T0150Z',
                          '20100808T0140Z', '20100808T0130Z',
                          '20100808T0120Z', '20100808T0110Z',
                          '20100808T0100Z', '20100808T0050Z',
                          '20100808T0040Z', '20100808T0030Z',
                          '20100808T0020Z', '20100808T0010Z',
                          '20100808T0000Z'])

        self.assertFalse(
            sequence.is_on_sequence(ISO8601Point('20100809T0005')))


if __name__ == '__main__':
    unittest.main()
