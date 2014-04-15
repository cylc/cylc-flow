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
from isodatetime.data import TimeInterval
from isodatetime.parsers import TimePointParser, TimeIntervalParser
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

    def cmp_(self, other):
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
        interval = TimeInterval(**unit_amounts)
        return ISO8601Interval(str(interval))

    def standardise(self):
        self.value = str(interval_parse(self.value))

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

        self.spec = i
        self.custom_point_parse_function = None
        if DUMP_FORMAT == PREV_DATE_TIME_FORMAT:
            self.custom_point_parse_function = point_parse
        self.time_parser = CylcTimeParser(
            str(self.context_start_point), str(self.context_end_point),
            num_expanded_year_digits=NUM_EXPANDED_YEAR_DIGITS,
            dump_format=DUMP_FORMAT,
            custom_point_parse_function=self.custom_point_parse_function
        )
        self.recurrence = self.time_parser.parse_recurrence(i)
        self.step = ISO8601Interval(str(self.recurrence.interval))
        self.value = str(self.recurrence)

    def get_interval(self):
        return self.step

    def get_offset(self):
        return self.offset

    def set_offset(self, i):
        """Alter state to offset the entire sequence."""
        self.offset = i
        start_point = self.context_start_point + self.offset
        end_point = self.context_end_point + self.offset
        self.time_parser = CylcTimeParser(
            str(start_point),
            str(end_point),
            num_expanded_year_digits=NUM_EXPANDED_YEAR_DIGITS,
            dump_format=DUMP_FORMAT,
            custom_point_parse_function=self.custom_point_parse_function
        )
        self.recurrence = self.time_parser.parse_recurrence(self.spec)
        self.value = str(self.recurrence)

    def is_on_sequence(self, p):
        """Return True if p is on-sequence."""
        return self.recurrence.get_is_valid(point_parse(p.value))

    def is_valid(self, p):
        """Return True if p is on-sequence and in-bounds."""
        return self.is_on_sequence(p)

    def get_prev_point(self, p):
        """Return the previous point < p, or None if out of bounds."""
        # may be None if out of the recurrence bounds
        res = None
        prv = self.recurrence.get_prev(point_parse(p.value))
        if prv:
            res = ISO8601Point(str(prv))
        return res

    def get_next_point(self, p):
        """Return the next point > p, or None if out of bounds."""
        p_iso_point = point_parse(p.value)
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point > p_iso_point:
                return ISO8601Point(str(recurrence_iso_point))
        return None

    def get_next_point_on_sequence(self, p):
        """Return the on-sequence point > p assuming that p is on-sequence,
        or None if out of bounds."""
        res = None
        nxt = self.recurrence.get_next(point_parse(p.value))
        if nxt:
            res = ISO8601Point(str(nxt))
        print res
        return res

    def get_first_point( self, p):
        """Return the first point >= to p, or None if out of bounds."""
        p_iso_point = point_parse(p.value)
        for recurrence_iso_point in self.recurrence:
            if recurrence_iso_point >= p_iso_point:
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
    m = re.match('(0?[0-9]|1[0-9]|2[0-3])', dep_section)
    if m:
        # back compat 0,6,12 etc.
        if only_detect_old:
            return True
        anchor = m.groups()[0]
        return "T%02d/P1D" % int(anchor)
    if only_detect_old:
        return False
    return dep_section


def init_from_cfg(cfg):
    """Initialise global variables (yuk) based on the configuration."""
    global point_parser
    global DUMP_FORMAT
    global NUM_EXPANDED_YEAR_DIGITS
    attempt_strptime_from_dump_format = False
    DUMP_FORMAT = "CCYYMMDDThhmm"
    NUM_EXPANDED_YEAR_DIGITS = (
        cfg['cylc']['cycle point num expanded year digits']
    )
    if NUM_EXPANDED_YEAR_DIGITS:
        DUMP_FORMAT = u"±XCCYYMMDDThhmm"
    time_zone = cfg['cylc']['cycle point time zone']
    if cfg['cylc']['cycle point format'] is not None:
        DUMP_FORMAT = cfg['cylc']['cycle point format']
        if u"±X" not in DUMP_FORMAT and NUM_EXPANDED_YEAR_DIGITS:
            raise IllegalValueError(
                'cycle time format',
                ('cylc', 'cycle point format'),
                DUMP_FORMAT
            )
    elif time_zone is not None:
        DUMP_FORMAT += time_zone
    else:
        DUMP_FORMAT += "Z"
    initial_cycle_time = cfg['scheduling']['initial cycle time']
    final_cycle_time = cfg['scheduling']['final cycle time']
    test_cycle_time = initial_cycle_time
    if initial_cycle_time is None:
        test_cycle_time = final_cycle_time
    if test_cycle_time is not None and re.match("\d+$", test_cycle_time):
        for key in cfg['scheduling']['dependencies']:
            if convert_old_cycler_syntax(key, only_detect_old=True):
                # Old cycling syntax is present.
                DUMP_FORMAT = PREV_DATE_TIME_FORMAT
                NUM_EXPANDED_YEAR_DIGITS = 0
                break
    point_parser = TimePointParser(
        allow_only_basic=False,
        allow_truncated=True,
        num_expanded_year_digits=NUM_EXPANDED_YEAR_DIGITS,
        dump_format=DUMP_FORMAT,
    )


def interval_parse(interval_string):
    try:
        return _interval_parse(interval_string).copy()
    except Exception:
        return -1 * _interval_parse(interval_string.replace("-", "")).copy()


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


YYYYMMDDHHmmss = '00010101000000'


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
