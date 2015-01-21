# -*- coding: utf-8 -*-

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
from isodatetime.parsers import TimePointParser, DurationParser
from isodatetime.timezone import (
    get_local_time_zone, get_local_time_zone_format)
from cylc.syntax_flags import set_syntax_version, VERSION_PREV, VERSION_NEW
from cylc.time_parser import CylcTimeParser
from cylc.cycling import (
    PointBase, IntervalBase, SequenceBase, PointParsingError,
    IntervalParsingError)
from parsec.validate import IllegalValueError

CYCLER_TYPE_ISO8601 = "iso8601"
CYCLER_TYPE_SORT_KEY_ISO8601 = "b"

MEMOIZE_LIMIT = 10000

OLD_STRPTIME_FORMATS_BY_LENGTH = {
    4: "%Y",
    6: "%Y%m",
    8: "%Y%m%d",
    10: "%Y%m%d%H",
    12: "%Y%m%d%H%M",
    14: "%Y%m%d%H%M%S",
}
DATE_TIME_FORMAT = "CCYYMMDDThhmm"
EXPANDED_DATE_TIME_FORMAT = "+XCCYYMMDDThhmm"
PREV_DATE_TIME_FORMAT = "%Y%m%d%H"
PREV_DATE_TIME_REC = re.compile("^\d{10}$")
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

    @classmethod
    def from_nonstandard_string(cls, point_string):
        """Standardise a date-time string."""
        return ISO8601Point(str(point_parse(point_string))).standardise()

    def add(self, other):
        """Add an Interval to self."""
        return ISO8601Point(self._iso_point_add(self.value, other.value))

    def __cmp__(self, other):
        # Compare other (point) to self.
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


class ISO8601Sequence(SequenceBase):

    """A sequence of ISO8601 date time points separated by an interval."""

    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601
    _MAX_CACHED_POINTS = 100

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
        else:
            self.context_start_point = ISO8601Point.from_nonstandard_string(
                context_start_point)
        if context_end_point is None:
            self.context_end_point = None
        else:
            self.context_end_point = ISO8601Point.from_nonstandard_string(
                context_end_point)

        self.offset = ISO8601Interval.get_null()

        recurrence_syntax = convert_old_cycler_syntax(
            dep_section, start_point=self.context_start_point)

        if not recurrence_syntax:
            raise ValueError(
                "ERROR: bad cycling sequence syntax: %s" % dep_section)

        self._cached_first_point_values = {}
        self._cached_next_point_values = {}
        self._cached_valid_point_booleans = {}

        self.spec = recurrence_syntax
        self.custom_point_parse_function = None
        if SuiteSpecifics.DUMP_FORMAT == PREV_DATE_TIME_FORMAT:
            self.custom_point_parse_function = point_parse
        self.abbrev_util = CylcTimeParser(
            self.context_start_point, self.context_end_point,
            num_expanded_year_digits=SuiteSpecifics.NUM_EXPANDED_YEAR_DIGITS,
            dump_format=SuiteSpecifics.DUMP_FORMAT,
            custom_point_parse_function=self.custom_point_parse_function,
            assumed_time_zone=SuiteSpecifics.ASSUMED_TIME_ZONE
        )
        self.recurrence = self.abbrev_util.parse_recurrence(recurrence_syntax)
        self.step = ISO8601Interval(str(self.recurrence.duration))
        self.value = str(self.recurrence)

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
        self.value = str(self.recurrence)

    def is_on_sequence(self, point):
        """Return True if point is on-sequence."""
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
        return res

    def get_nearest_prev_point(self, point):
        """Return the largest point < some arbitrary point."""
        if self.is_on_sequence(point):
            return self.get_prev_point(point)
        p_iso_point = point_parse(point.value)
        prev_iso_point = None
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point > p_iso_point:
                # Technically, >=, but we already test for this above.
                break
            prev_iso_point = recurrence_iso_point
        if prev_iso_point is None:
            return None
        return ISO8601Point(str(prev_iso_point))

    def get_next_point(self, point):
        """Return the next point > p, or None if out of bounds."""
        try:
            return ISO8601Point(self._cached_next_point_values[point.value])
        except KeyError:
            pass
        p_iso_point = point_parse(point.value)
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point > p_iso_point:
                next_point_value = str(recurrence_iso_point)
                if (len(self._cached_next_point_values) >
                        self._MAX_CACHED_POINTS):
                    self._cached_next_point_values.popitem()
                self._cached_next_point_values[point.value] = next_point_value
                return ISO8601Point(next_point_value)
        return None

    def get_next_point_on_sequence(self, point):
        """Return the on-sequence point > point assuming that point is
        on-sequence, or None if out of bounds."""
        result = None
        next_point = self.recurrence.get_next(point_parse(point.value))
        if next_point:
            result = ISO8601Point(str(next_point))
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
                if (len(self._cached_first_point_values) >
                        self._MAX_CACHED_POINTS):
                    self._cached_first_point_values.popitem()
                self._cached_first_point_values[point.value] = (
                    first_point_value)
                return ISO8601Point(first_point_value)
        return None

    def get_start_point( self ):
        """Return the first point in this sequence, or None."""
        for recurrence_iso_point in self.recurrence:
            return ISO8601Point(str(recurrence_iso_point))
        return None

    def get_stop_point(self):
        """Return the last point in this sequence, or None if unbounded."""
        if (self.recurrence.repetitions is not None or (
                (self.recurrence.start_point is not None or
                 self.recurrence.min_point is not None) and
                (self.recurrence.end_point is not None or
                 self.recurrence.max_point is not None))):
            for recurrence_iso_point in self.recurrence:
                pass
            return ISO8601Point(str(recurrence_iso_point))
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


def convert_old_cycler_syntax(dep_section, only_detect_old=False,
                              start_point=None):
    """Convert old cycler syntax into our Cylc-ISO8601 format."""
    for re_old_format, unit in [
            ("^Daily\(\s*(\d+)\s*,\s*(\d+)\s*\)$", "D"),
            ("^Monthly\(\s*(\d+)\s*,\s*(\d+)\s*\)$", "M"),
            ("^Yearly\(\s*(\d+)\s*,\s*(\d+)\s*\)$", "Y")]:
        results = re.search(re_old_format, dep_section)
        if not results:
            continue
        if only_detect_old:
            return True
        anchor, step = results.groups()
        step = ISO8601Interval("P%s%s" % (step, unit))
        return _get_old_anchor_step_recurrence(anchor, step, start_point)
    # Check for the hourly syntax.
    results = re.match('(0?[0-9]|1[0-9]|2[0-3])$', dep_section)
    if results:
        # back compat 0,6,12 etc.
        if only_detect_old:
            return True
        anchor = results.groups()[0]
        return "T%02d/PT24H" % int(anchor)
    if only_detect_old:
        return False
    return dep_section


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
    initial_cycle_point = cfg['scheduling']['initial cycle point']
    final_cycle_point = cfg['scheduling']['final cycle point']
    assume_utc = cfg['cylc']['UTC mode']
    cycling_mode = cfg['scheduling']['cycling mode']

    # Detect (date-time) previous-format cycle point usage.
    has_prev_format_cycle_point = (
        (initial_cycle_point is not None and
         PREV_DATE_TIME_REC.search(initial_cycle_point)) or
        (final_cycle_point is not None and
         PREV_DATE_TIME_REC.search(final_cycle_point))
    )
    if (has_prev_format_cycle_point and
            custom_dump_format != PREV_DATE_TIME_FORMAT):
        set_syntax_version(
            VERSION_PREV,
            "initial/final cycle point format: CCYYMMDDhh"
        )

    # Detect (date-time) ISO 8601-format cycle point usage.
    has_new_format_cycle_point = (
        (initial_cycle_point is not None and
         NEW_DATE_TIME_REC.search(initial_cycle_point)) or
        (final_cycle_point is not None and
         NEW_DATE_TIME_REC.search(final_cycle_point))
    )
    if has_new_format_cycle_point:
        set_syntax_version(
            VERSION_NEW,
            "initial/final cycle point format: non-numeric (ISO 8601?)"
        )

    # Loop over all dependency sub-sections and detect cycler syntax versions.
    dep_sections = list(cfg['scheduling']['dependencies'])
    while dep_sections:
        dep_section = dep_sections.pop(0)
        if re.search("(?![^(]+\)),", dep_section):
            dep_sections.extend([i.strip() for i in
                                    re.split("(?![^(]+\)),", dep_section)])
            continue
        if dep_section == "graph":
            if cfg['scheduling']['dependencies']['graph']:
                # Using async graph in date-time cycling.
                set_syntax_version(
                    VERSION_PREV,
                    "[scheduling][[dependencies]]graph: mixed with " +
                    "date-time cycling"
                )
                custom_dump_format = PREV_DATE_TIME_FORMAT
                num_expanded_year_digits = 0
            continue
        if convert_old_cycler_syntax(dep_section,
                                     only_detect_old=True):
            # Detected prev-format (old) syntax.
            set_syntax_version(
                VERSION_PREV,
                "[scheduling][[dependencies]][[[%s]]]: old-style cycling" %
                dep_section
            )
            custom_dump_format = PREV_DATE_TIME_FORMAT
            num_expanded_year_digits = 0
        else:
            # Detected new-style syntax.
            set_syntax_version(
                VERSION_NEW,
                ("[scheduling][[dependencies]][[[%s]]]: " % dep_section) +
                "ISO 8601-style cycling"
            )

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
    custom_point_parse_function = None
    if SuiteSpecifics.DUMP_FORMAT == PREV_DATE_TIME_FORMAT:
        custom_point_parse_function = point_parse
    SuiteSpecifics.abbrev_util = CylcTimeParser(
        None, None,
        num_expanded_year_digits=SuiteSpecifics.NUM_EXPANDED_YEAR_DIGITS,
        dump_format=SuiteSpecifics.DUMP_FORMAT,
        custom_point_parse_function=custom_point_parse_function,
        assumed_time_zone=SuiteSpecifics.ASSUMED_TIME_ZONE
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
        )
    )


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
        # Includes prev-format point strings.
        try:
            point = SuiteSpecifics.point_parser.strptime(
                point_string, SuiteSpecifics.DUMP_FORMAT)
        except ValueError as e:
            strptime_string = _get_old_strptime_format(point_string)
            if strptime_string is not None:
                return SuiteSpecifics.point_parser.strptime(
                    point_string, strptime_string)
        else:
            return point
    # Attempt to parse it in ISO 8601 format then...
    try:
        point = SuiteSpecifics.point_parser.parse(point_string)  # Fail?
        return point
    except ValueError:
        strptime_string = _get_old_strptime_format(point_string)
        if strptime_string is None:
            raise
        set_syntax_version(
            VERSION_PREV,
            "non-ISO-8601-compatible cycle point: %s" % point_string
        )
        return SuiteSpecifics.point_parser.strptime(
            point_string, strptime_string)


def _get_old_strptime_format(point_string):
    """Return an adjusted strptime format depending on the string length."""
    try:
        return OLD_STRPTIME_FORMATS_BY_LENGTH[len(point_string)]
    except KeyError:
        return None


def test():
    """Run some simple tests for date-time cycling."""
    cylc_config = {"cylc": {"cycle point num expanded year digits": 0,
                            "cycle point format": None,
                            "cycle point time zone": None}}
    init_from_cfg(cylc_config)
    p_start = ISO8601Point('20100808T00')
    p_stop = ISO8601Point('20100808T02')
    i = ISO8601Interval('PT6H')
    print p_start - i
    print p_stop + i

    print
    r = ISO8601Sequence('PT10M', str(p_start), str(p_stop),)
    r.set_offset(- ISO8601Interval('PT10M'))
    p = r.get_next_point(ISO8601Point('20100808T0000'))
    print p
    while p and p < p_stop:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_next_point(p)
    print
    while p and p >= p_start:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_prev_point(p)

    print
    print r.is_on_sequence(ISO8601Point('20100809T0005'))

if __name__ == '__main__':
    test()
