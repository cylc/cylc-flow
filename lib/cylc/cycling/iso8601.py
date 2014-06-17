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

import re
import isodatetime.data
from isodatetime.dumpers import TimePointDumper
from isodatetime.parsers import TimePointParser, TimeIntervalParser
from isodatetime.timezone import (
    get_local_time_zone, get_local_time_zone_format)
from cylc.time_parser import CylcTimeParser
from cylc.cycling import PointBase, IntervalBase
from parsec.validate import IllegalValueError

# TODO - Consider copy vs reference of points, intervals, sequences
# TODO - Use context points properly
# TODO - ignoring anchor in back-compat sections


CYCLER_TYPE_ISO8601 = "iso8601"
CYCLER_TYPE_SORT_KEY_ISO8601 = "b"

MEMOIZE_LIMIT = 10000

interval_parser = TimeIntervalParser()

OLD_STRPTIME_FORMATS_BY_LENGTH = {
    4: "%Y",
    6: "%Y%m",
    8: "%Y%m%d",
    10: "%Y%m%d%H",
    12: "%Y%m%d%H%M",
    14: "%Y%m%d%H%M%S",
}
PREV_DATE_TIME_FORMAT = "%Y%m%d%H"


# The following must be set by calling the init_from_cfg function.
# TODO: this is yukky. Is there a better alternative?
point_parser = None
NUM_EXPANDED_YEAR_DIGITS = None
DUMP_FORMAT = None
ASSUMED_TIME_ZONE = None


def memoize(function):
    """This stores results for a given set of inputs to a function.

    The inputs and results of the function must be immutable.
    Keyword arguments are not allowed.

    To avoid memory leaks, only the first 10000 separate input
    permutations are cached for a given function.

    """
    inputs_results = {}
    def _wrapper(*args):
        try:
            return inputs_results[args]
        except KeyError:
            results = function(*args)
            if len(inputs_results) > MEMOIZE_LIMIT:
                # Full up, no more room.
                return results
            inputs_results[args] = results
            return results
    return _wrapper


class ISO8601Point(PointBase):

    """A single point in an ISO8601 date time sequence."""

    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601

    @classmethod
    def from_nonstandard_string(cls, point_string):
        return ISO8601Point(str(point_parse(point_string))).standardise()

    def add(self, other):
        return ISO8601Point(self._iso_point_add(self.value, other.value))

    def __cmp__(self, other):
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self._iso_point_cmp(self.value, other.value)

    def standardise(self):
        self.value = str(point_parse(self.value))
        return self

    def sub(self, other):
        if isinstance(other, ISO8601Point):
            return ISO8601Interval(
                self._iso_point_sub_point(self.value, other.value))
        return ISO8601Point(
            self._iso_point_sub_interval(self.value, other.value))

    @staticmethod
    @memoize
    def _iso_point_add(point_string, interval_string):
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point + interval)

    @staticmethod
    @memoize
    def _iso_point_cmp(point_string, other_point_string):
        point = point_parse(point_string)
        other_point = point_parse(other_point_string)
        return cmp(point, other_point)

    @staticmethod
    @memoize
    def _iso_point_sub_interval(point_string, interval_string):
        point = point_parse(point_string)
        interval = interval_parse(interval_string)
        return str(point - interval)

    @staticmethod
    @memoize
    def _iso_point_sub_point(point_string, other_point_string):
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
        return ISO8601Interval("P0Y")

    def get_inferred_child(self, string):
        """Return an instance with 'string' amounts of my non-zero units."""
        interval = interval_parse(self.value)
        amount_per_unit = int(string)
        unit_amounts = {}
        for attribute in ["years", "months", "weeks", "days",
                          "hours", "minutes", "seconds"]:
            if getattr(interval, attribute):
                unit_amounts[attribute] = amount_per_unit
        interval = isodatetime.data.TimeInterval(**unit_amounts)
        return ISO8601Interval(str(interval))

    def standardise(self):
        self.value = str(interval_parse(self.value))
        return self

    def add(self, other):
        if isinstance(other, ISO8601Interval):
            return ISO8601Interval(
                self._iso_interval_add(self.value, other.value))
        return ISO8601Point(
                self._iso_point_add(other.value, self.value))

    def cmp_(self, other):
        return self._iso_interval_cmp(self.value, other.value)

    def sub(self, other):
        return ISO8601Interval(
            self._iso_interval_sub(self.value, other.value))

    def __abs__(self):
        return ISO8601Interval(
            self._iso_interval_abs(self.value, self.NULL_INTERVAL_STRING))

    def __mul__(self, m):
        # the suite runahead limit is a multiple of the smallest sequence interval
        return ISO8601Interval(self._iso_interval_mul(self.value, m))

    def __nonzero__(self):
        return self._iso_interval_nonzero(self.value)

    @staticmethod
    @memoize
    def _iso_interval_abs(interval_string, other_interval_string):
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        if interval < other:
            return str(interval * -1)
        return interval_string

    @staticmethod
    @memoize
    def _iso_interval_add(interval_string, other_interval_string):
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval + other)

    @staticmethod
    @memoize
    def _iso_interval_cmp(interval_string, other_interval_string):
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return cmp(interval, other)

    @staticmethod
    @memoize
    def _iso_interval_sub(interval_string, other_interval_string):
        interval = interval_parse(interval_string)
        other = interval_parse(other_interval_string)
        return str(interval - other)

    @staticmethod
    @memoize
    def _iso_interval_mul(interval_string, factor):
        interval = interval_parse(interval_string)
        return str(interval * factor)

    @staticmethod
    @memoize
    def _iso_interval_nonzero(interval_string):
        interval = interval_parse(interval_string)
        return bool(interval)


class ISO8601Sequence(object):
    """
    A sequence of ISO8601 date time points separated by an interval.
    """

    TYPE = CYCLER_TYPE_ISO8601
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_ISO8601
    _MAX_CACHED_POINTS = 100

    @classmethod
    def get_async_expr(cls, start_point=None):
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

        i = convert_old_cycler_syntax(dep_section)

        if not i:
            raise "ERROR: iso8601 cycling init!"

        self._cached_first_point_values = {}
        self._cached_next_point_values = {}
        self._cached_valid_point_booleans = {}

        self.spec = i
        self.custom_point_parse_function = None
        if DUMP_FORMAT == PREV_DATE_TIME_FORMAT:
            self.custom_point_parse_function = point_parse

        self.time_parser = CylcTimeParser(
            self.context_start_point, self.context_end_point,
            num_expanded_year_digits=NUM_EXPANDED_YEAR_DIGITS,
            dump_format=DUMP_FORMAT,
            custom_point_parse_function=self.custom_point_parse_function,
            assumed_time_zone=ASSUMED_TIME_ZONE
        )
        self.recurrence = self.time_parser.parse_recurrence(i)
        self.step = ISO8601Interval(str(self.recurrence.interval))
        self.value = str(self.recurrence)

    def get_interval(self):
        return self.step

    def get_offset(self):
        return self.offset

    def set_offset(self, offset):
        """Alter state to offset the entire sequence."""
        if self.recurrence.start_point is not None:
            self.recurrence.start_point -= interval_parse(str(offset))
        if self.recurrence.end_point is not None:
            self.recurrence.end_point -= interval_parse(str(offset))
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

    def get_first_point( self, point):
        """Return the first point >= to poing, or None if out of bounds."""
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

    def get_stop_point( self ):
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
        if self.TYPE != other.TYPE:
            return False
        if self.value == other.value:
            return True
        return False


def convert_old_cycler_syntax(dep_section, only_detect_old=False):
    """Convert old cycler syntax into our Cylc-ISO8601 format."""
    m = re.match('^Daily\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section)
    if m:
        # back compat Daily()
        if only_detect_old:
            return True
        anchor, step = m.groups()
        anchor = str(ISO8601Point.from_nonstandard_string(anchor))
        return anchor + '/P' + step + 'D'
    m = re.match('^Monthly\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section)
    if m:
        # back compat Monthly()
        if only_detect_old:
            return True
        anchor, step = m.groups()
        anchor = str(ISO8601Point.from_nonstandard_string(anchor))
        return anchor + '/P' + step + 'M'
    m = re.match('^Yearly\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section)
    if m:
        # back compat Yearly()
        if only_detect_old:
            return True
        anchor, step = m.groups()
        anchor = str(ISO8601Point.from_nonstandard_string(anchor))
        return anchor + '/P' + step + 'Y'
    m = re.match('(0?[0-9]|1[0-9]|2[0-3])$', dep_section)
    if m:
        # back compat 0,6,12 etc.
        if only_detect_old:
            return True
        anchor = m.groups()[0]
        return "T%02d/PT24H" % int(anchor)
    if only_detect_old:
        return False
    return dep_section


def get_backwards_compatibility_mode():
    """Return whether we are in the old cycling syntax regime."""
    return DUMP_FORMAT == PREV_DATE_TIME_FORMAT


def init_from_cfg(cfg):
    """Initialise global variables (yuk) based on the configuration."""
    num_expanded_year_digits = cfg['cylc'][
        'cycle point num expanded year digits']
    time_zone = cfg['cylc']['cycle point time zone']
    custom_dump_format = cfg['cylc']['cycle point format']
    initial_cycle_time = cfg['scheduling']['initial cycle time']
    final_cycle_time = cfg['scheduling']['final cycle time']
    assume_utc = cfg['cylc']['UTC mode']
    calendar = cfg['cylc']['calendar']
    test_cycle_time = initial_cycle_time
    if initial_cycle_time is None:
        test_cycle_time = final_cycle_time
    if test_cycle_time is not None and re.match("\d+$", test_cycle_time):
        dep_sections = list(cfg['scheduling']['dependencies'])
        while dep_sections:
            dep_section = dep_sections.pop(0)
            if re.search("(?![^(]+\)),", dep_section):
                dep_sections.extend([i.strip() for i in 
                                     re.split("(?![^(]+\)),", dep_section)])
                continue
            if ((dep_section == "graph" and
                    cfg['scheduling']['dependencies']['graph']) or
                    convert_old_cycler_syntax(dep_section,
                                              only_detect_old=True)):
                # Old cycling syntax is present.
                custom_dump_format = PREV_DATE_TIME_FORMAT
                num_expanded_year_digits = 0
                break
    init(
        num_expanded_year_digits=num_expanded_year_digits,
        custom_dump_format=custom_dump_format,
        time_zone=time_zone,
        assume_utc=assume_utc,
        calendar=calendar
    )


def init(num_expanded_year_digits=0, custom_dump_format=None, time_zone=None,
         assume_utc=False, calendar="gregorian"):
    """Initialise global variables (yuk)."""
    global point_parser
    global DUMP_FORMAT
    global NUM_EXPANDED_YEAR_DIGITS
    global ASSUMED_TIME_ZONE

    if calendar == "360":
        isodatetime.data.set_360_calendar()

    if time_zone is None:
        if assume_utc:
            time_zone = "Z"
            time_zone_hours_minutes = (0, 0)
        else:
            time_zone = get_local_time_zone_format(reduced_mode=True)
            time_zone_hours_minutes = get_local_time_zone()
    else:       
        time_zone_hours_minutes = TimePointDumper().get_time_zone(time_zone)
    ASSUMED_TIME_ZONE = time_zone_hours_minutes
    NUM_EXPANDED_YEAR_DIGITS = num_expanded_year_digits
    if custom_dump_format is None:
        if num_expanded_year_digits > 0:
            DUMP_FORMAT = u"±XCCYYMMDDThhmm" + time_zone
        else:
            DUMP_FORMAT = "CCYYMMDDThhmm" + time_zone
        
    else:
        DUMP_FORMAT = custom_dump_format
        if u"±X" not in custom_dump_format and num_expanded_year_digits:
            raise IllegalValueError(
                'cycle time format',
                ('cylc', 'cycle point format'),
                DUMP_FORMAT
            )
    point_parser = TimePointParser(
        allow_only_basic=False,
        allow_truncated=True,
        num_expanded_year_digits=NUM_EXPANDED_YEAR_DIGITS,
        dump_format=DUMP_FORMAT,
        assumed_time_zone=time_zone_hours_minutes
    )


def interval_parse(interval_string):
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
    return interval_parser.parse(interval_string)


def point_parse(point_string):
    return _point_parse(point_string).copy()


@memoize
def _point_parse(point_string):
    if "%" in DUMP_FORMAT:
        try:
            point = point_parser.strptime(point_string, DUMP_FORMAT)
        except ValueError as e:
            strptime_string = _get_old_strptime_format(point_string)
            if strptime_string is not None:
                return point_parser.strptime(point_string, strptime_string)
    try:
        point = point_parser.parse(point_string)  # Fail?
        return point
    except ValueError:
        strptime_string = _get_old_strptime_format(point_string)
        if strptime_string is None:
            raise
        return point_parser.strptime(point_string, strptime_string)


def _get_old_strptime_format(point_string):
    try:
        return OLD_STRPTIME_FORMATS_BY_LENGTH[len(point_string)]
    except KeyError:
        return None


if __name__ == '__main__':
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
