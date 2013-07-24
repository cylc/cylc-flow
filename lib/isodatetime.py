# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# (C) British Crown Copyright 2013 Met Office.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-----------------------------------------------------------------------------

import copy
import re
import unittest


DAYS_OF_MONTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DAYS_OF_MONTHS_LEAP = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

WEEK_DAY_START_REFERENCE = {"calendar": (2000, 1, 3),
                            "ordinal": (2000, 3)}



class TimeRecurrenceParser(object):

    """Parser for ISO 8601 recurrence expressions.

    Keyword arguments:
    timepoint_parser (default None) should be an instance of
    TimePointParser, or None to use a normal TimePointParser instance.
    timeinterval_parser (default None) should be an instance of
    TimeIntervalParser, or None to generate a normal
    TimeIntervalParser.

    Callable (via self.parse method) with an ISO 8601-compliant
    recurrence pattern - this returns a TimeRecurrence instance.

    """

    RECURRENCE_REGEXES = [
         re.compile(r"^R(?P<reps>\d+)/(?P<start>[^P][^/]*)/(?P<end>[^P].*)$"),
         re.compile(r"^R(?P<reps>\d+)?/(?P<start>[^P][^/]*)/(?P<intv>P.+)$"),
         re.compile(r"^R(?P<reps>\d+)?/(?P<intv>P.+)/(?P<end>[^P].*)$")]

    def __init__(self, timepoint_parser=None, timeinterval_parser=None):
        if timepoint_parser is None:
            self.timepoint_parser = TimePointParser()
        else:
            self.timepoint_parser = timepoint_parser
        if timeinterval_parser is None:
            self.timeinterval_parser = TimeIntervalParser()
        else:
            self.timepoint_parser = timeinterval_parser

    def parse(self, expression):
        """Parse a recurrence string into a TimeRecurrence instance."""
        for regex in self.RECURRENCE_REGEXES:
            result = regex.search(expression)
            if not result:
                continue
            result_map = result.groupdict()
            repetitions = None
            start_point = None
            end_point = None
            interval = None
            if "reps" in result_map and result_map["reps"] is not None:
                repetitions = int(result_map["reps"])
            if "start" in result_map:
                start_point = self.timepoint_parser.parse(result_map["start"])
            if "end" in result_map:
                end_point = self.timepoint_parser.parse(result_map["end"])
            if "intv" in result_map:
                interval = self.timeinterval_parser.parse(
                                             result_map["intv"])
            return TimeRecurrence(repetitions=repetitions,
                                  start_point=start_point,
                                  end_point=end_point,
                                  interval=interval)
        raise TimeSyntaxError("Not a supported ISO 8601 recurrence pattern: %s" %
                              expression)

    def get_tests(self):
        """Run a series of self-tests.

        The amount of parsing in this class is quite small, so not many
        tests are needed for this part.

        """
        test_points = ["-100024-02-10T17:00:00-12:30",
                       "+000001-W45-7T06Z", "1001W011",
                       "1955W051T06,5Z", "1999-06-01",
                       "1967-056", "+5002000830T235902,345",
                       "1765-W04"]
        for reps in [None, 1, 2, 3, 10]:
            if reps is None:
                reps_string = ""
            else:
                reps_string = str(reps)
            point_parser = TimePointParser()
            interval_parser = TimeIntervalParser()
            for point_expr in test_points:
                interval_tests = interval_parser.get_tests()
                start_point = point_parser.parse(point_expr)
                for interval_expr, interval_result in interval_tests:
                    interval = interval_parser.parse(interval_expr)
                    end_point = start_point + interval
                    if reps is not None:
                        expr_1 = ("R" + reps_string + "/" + str(start_point) +
                                  "/" + str(end_point))
                        yield expr_1, {"repetitions": reps,
                                       "start_point": start_point,
                                       "end_point": end_point}
                    expr_3 = ("R" + reps_string + "/" + str(start_point) +
                              "/" + str(interval))
                    yield expr_3, {"repetitions": reps,
                                   "start_point": start_point,
                                   "interval": interval}
                    expr_4 = ("R" + reps_string + "/" + str(interval) + "/" +
                              str(end_point))
                    yield expr_4, {"repetitions": reps, "interval": interval,
                                   "end_point": end_point}

    __call__ = parse


class TimePointParser(object):

    """Container for ISO 8601 date/time expressions.

    Keyword arguments:
    num_expanded_year_digits (default 2) specifies the extra year
    digits allowed by the ISO standard - for example, 1995 can be
    written as +001995 with 2 extra year digits.

    allow_truncated (default False) specifies that ISO 8601:2000
    truncations are allowed (not allowed in the ISO 8601:2004
    standard which supersedes it).

    allow_only_basic (default False) specifies that only the basic
    forms of date and time in the ISO standard are allowed (no
    extraneous punctuation). This means that "2000-01-02T01:14:02"
    is not allowed, and must be written as "20000102T011402".

    assume_utc (default False) specifies that dates and times without
    timezone information should be assumed UTC (Z). Otherwise, these
    will be converted to the local timezone.

    format_function (default None) should be a callable that takes a
    TimePoint instance created by this parser and returns a custom
    string representation such as "20150304T0103". This is called on
    str(timepoint_instance). If None, the default TimePoint
    formatting will be applied.

    """

    DATE_EXPRESSIONS = {"basic": {"complete": u"""
ccYYMMDD
±ΫccYYMMDD
ccYYDDD
±ΫccYYDDD
ccYYWwwD
±ΫccYYWwwD""",
                                  "reduced": u"""
ccYY-MM       # Deviation? Not clear if "basic" or "extended" in standard.
ccYY
cc
±ΫccYY-MM     # Deviation? Not clear if "basic" or "extended" in standard.
±ΫccYY
±Ϋcc
ccYYWww
±ΫccYYWww""",
                                  "truncated": u"""
-YYMM
-YY
--MMDD
--MM
---DD
YYMMDD
YYDDD
-DDD
YYWwwD
YYWww
-ỵWwwD
-ỵWww
-WwwD
-Www
-W-D
"""},
                        "extended": {"complete": u"""
ccYY-MM-DD
±ΫccYY-MM-DD
ccYY-DDD
±ΫccYY-DDD
ccYY-Www-D
±ΫccYY-Www-D""",
                                     "reduced": u"""
ccYY-MM
±ΫccYY-MM
ccYY-Www
±ΫccYY-Www""",
                                     "truncated": u"""
-YY-MM
--MM-DD
YY-MM-DD
YY-DDD
-DDD          # Deviation from standard ?
YY-Www-D
YY-Www
-ỵ-WwwD
-ỵ-Www
-Www-D
"""}}

    TIME_EXPRESSIONS = {"basic": {"complete": u"""
# No Time Zone
hhmmss

# No Time Zone - decimals
hhmmss,sṡ
hhmm,mṁ
hh,hḣ
""",
                                  "reduced": u"""
# No Time Zone
hhmm
hh

# No Time Zone - decimals
""",
                                  "truncated": u"""
# No Time Zone
-mmss
-mm
--ss

# No Time Zone - decimals
-mmss,sṡ
-mm,mṁ
--ss,sṡ
"""},
                        "extended": {"complete": u"""
# No Time Zone
hh:mm:ss

# No Time Zone - decimals
hh:mm:ss,sṡ
hh:mm,mṁ
hh,hḣ          # Deviation? Not allowed in standard ?
""",
                                     "reduced": u"""
# No Time Zone
hh:mm
hh             # Deviation? Not allowed in standard ?
""",
                                  "truncated": u"""
# No Time Zone
-mm:ss
-mm             # Deviation? Not allowed in standard ?
--ss            # Deviation? Not allowed in standard ?

# No Time Zone - decimals
-mm:ss,sṡ
-mm,mṁ          # Deviation? Not allowed in standard ?
--ss,sṡ         # Deviation? Not allowed in standard ?
"""}}

    TIMEZONE_EXPRESSIONS = {"basic": u"""
Z
±hh
±hhmm
""",
                            "extended": u"""
Z
±hh             # Deviation? Not allowed in standard?
±hh:mm
"""}

    DATE_CHAR_REGEXES = [(u"±", "(?P<year_sign>[+-])"),
                         (u"cc", "(?P<century>\d\d)"),
                         (u"YY", "(?P<year_of_century>\d\d)"),
                         (u"MM", "(?P<month_of_year>\d\d)"),
                         (u"DDD", "(?P<day_of_year>\d\d\d)"),
                         (u"DD", "(?P<day_of_month>\d\d)"),
                         (u"Www", "W(?P<week_of_year>\d\d)"),
                         (u"D", "(?P<day_of_week>\d)"),
                         (u"ỵ", "(?P<year_of_decade>\d)"),
                         (u"^---", "(?P<truncated>---)"),
                         (u"^--", "(?P<truncated>--)"),
                         (u"^-", "(?P<truncated>-)"),
                         (u"^~", "(?P<truncated>)")]
    TIME_CHAR_REGEXES = [(u"(?<=^hh)mm", "(?P<minute_of_hour>\d\d)"),
                         (u"(?<=^hh:)mm", "(?P<minute_of_hour>\d\d)"),
                         (u"(?<=^-)mm", "(?P<minute_of_hour>\d\d)"),
                         (u"^hh", "(?P<hour_of_day>\d\d)"),
                         (u",hḣ", "[,.](?P<hour_of_day_decimal>\d+)"),
                         (u",mṁ", "[,.](?P<minute_of_hour_decimal>\d+)"),
                         (u"ss", "(?P<second_of_minute>\d\d)"),
                         (u",sṡ", "[,.](?P<second_of_minute_decimal>\d+)"),
                         (u"^--", "(?P<truncated>--)"),
                         (u"^-", "(?P<truncated>-)")]
    TIMEZONE_CHAR_REGEXES = [
                         (u"(?<=±hh)mm", "(?P<time_zone_minute>\d\d)"),
                         (u"(?<=±hh:)mm", "(?P<time_zone_minute>\d\d)"),
                         (u"(?<=±)hh", "(?P<time_zone_hour>\d\d)"),
                         (u"±", "(?P<time_zone_sign>[+-])"),
                         (u"Z", "(?P<time_zone_utc>Z)")]
    TIME_DESIGNATOR = "T"

    # Note: test dates assume 2 expanded year digits.
    TEST_DATE_EXPRESSIONS = {"basic": {"complete": {
           "00440104": {"year": 44, "month_of_year": 1, "day_of_month": 4},
           "+5002000830": {"year": 500200, "month_of_year": 8,
                           "day_of_month": 30, "expanded_year_digits": 2},
           "-0000561113": {"year": -56, "month_of_year": 11,
                           "day_of_month": 13, "expanded_year_digits": 2},
           "-1000240210": {"year": -100024, "month_of_year": 2,
                           "day_of_month": 10, "expanded_year_digits": 2},
           "1967056": {"year": 1967, "day_of_year": 56},
           "+123456078": {"year": 123456, "day_of_year": 78,
                          "expanded_year_digits": 2},
           "-004560134": {"year": -4560, "day_of_year": 134,
                          "expanded_year_digits": 2},
           "1001W011": {"year": 1001, "week_of_year": 1, "day_of_week": 1},
           "+000001W457": {"year": 1, "week_of_year": 45, "day_of_week": 7,
                           "expanded_year_digits": 2},
           "-010001W053": {"year": -10001, "week_of_year": 5,
                           "day_of_week": 3, "expanded_year_digits": 2}},
                                       "reduced": {
           "4401-03": {"year": 4401, "month_of_year": 3},
           "1982": {"year": 1982},
           "19": {"year": 1900},
           "+056789-01": {"year": 56789, "month_of_year": 1,
                          "expanded_year_digits": 2},
           "-000001-12": {"year": -1, "month_of_year": 12,
                          "expanded_year_digits": 2},
           "-789123": {"year": -789123, "expanded_year_digits": 2},
           "+450001": {"year": 450001, "expanded_year_digits": 2},
         # The following cannot be parsed - looks like truncated -YYMM.
         #  "-0023": {"year": -2300, "expanded_year_digits": 2},
           "+5678": {"year": 567800, "expanded_year_digits": 2},
           "1765W04": {"year": 1765, "week_of_year": 4},
           "+001765W44": {"year": 1765, "week_of_year": 44,
                          "expanded_year_digits": 2},
           "-123321W50": {"year": -123321, "week_of_year": 50,
                          "expanded_year_digits": 2}},
                                       "truncated": {
           "-9001": {"year": 90, "month_of_year": 1,
                     "truncated": True,
                     "truncated_property": "year_of_century"},
           "960328": {"year": 96, "month_of_year": 3,
                      "day_of_month": 28,
                      "truncated": True,
                      "truncated_property": "year_of_century"},
           "-90": {"year": 90, "truncated": True,
                   "truncated_property": "year_of_century"},
           "--0501": {"month_of_year": 5, "day_of_month": 1,
                      "truncated": True},
           "--12": {"month_of_year": 12, "truncated": True},
           "---30": {"day_of_month": 30, "truncated": True},
           "98354": {"year": 98, "day_of_year": 354, "truncated": True,
                     "truncated_property": "year_of_century"},
           "-034": {"day_of_year": 34, "truncated": True},
           "00W031": {"year": 0, "week_of_year": 3, "day_of_week": 1,
                      "truncated": True,
                      "truncated_property": "year_of_century"},
           "99W34": {"year": 99, "week_of_year": 34, "truncated": True,
                     "truncated_property": "year_of_century"},
           "-1W02": {"year": 1, "week_of_year": 2,
                     "truncated": True,
                     "truncated_property": "year_of_decade"},
           "-W031": {"week_of_year": 3, "day_of_week": 1, "truncated": True},
           "-W32": {"week_of_year": 32, "truncated": True},
           "-W-1": {"day_of_week": 1, "truncated": True}}},
                          "extended": {"complete": {
           "0044-01-04": {"year": 44, "month_of_year": 1, "day_of_month": 4},
           "+500200-08-30": {"year": 500200, "month_of_year": 8,
                             "day_of_month": 30, "expanded_year_digits": 2},
           "-000056-11-13": {"year": -56, "month_of_year": 11,
                             "day_of_month": 13, "expanded_year_digits": 2},
           "-100024-02-10": {"year": -100024, "month_of_year": 2,
                             "day_of_month": 10, "expanded_year_digits": 2},
           "1967-056": {"year": 1967, "day_of_year": 56},
           "+123456-078": {"year": 123456, "day_of_year": 78,
                           "expanded_year_digits": 2},
           "-004560-134": {"year": -4560, "day_of_year": 134,
                           "expanded_year_digits": 2},
           "1001-W01-1": {"year": 1001, "week_of_year": 1, "day_of_week": 1},
           "+000001-W45-7": {"year": 1, "week_of_year": 45, "day_of_week": 7,
                             "expanded_year_digits": 2},
           "-010001-W05-3": {"year": -10001, "week_of_year": 5,
                             "day_of_week": 3, "expanded_year_digits": 2}},
                                       "reduced": {
           "4401-03": {"year": 4401, "month_of_year": 3},
           "1982": {"year": 1982},
           "19": {"year": 1900},
           "+056789-01": {"year": 56789, "month_of_year": 1,
                          "expanded_year_digits": 2},
           "-000001-12": {"year": -1, "month_of_year": 12,
                          "expanded_year_digits": 2},
           "-789123": {"year": -789123, "expanded_year_digits": 2},
           "+450001": {"year": 450001, "expanded_year_digits": 2},
           # The following cannot be parsed - looks like truncated -YYMM.
           #  "-0023": {"year": -2300, "expanded_year_digits": 2},
           "+5678": {"year": 567800, "expanded_year_digits": 2},
           "1765-W04": {"year": 1765, "week_of_year": 4},
           "+001765-W44": {"year": 1765, "week_of_year": 44,
                           "expanded_year_digits": 2},
           "-123321-W50": {"year": -123321, "week_of_year": 50,
                           "expanded_year_digits": 2}},
                                       "truncated": {
           "-9001": {"year": 90, "month_of_year": 1,
                     "truncated": True,
                     "truncated_property": "year_of_century"},
           "96-03-28": {"year": 96, "month_of_year": 3,
                        "day_of_month": 28,
                        "truncated": True,
                        "truncated_property": "year_of_century"},
           "-90": {"year": 90, "truncated": True,
                   "truncated_property": "year_of_century"},
           "--05-01": {"month_of_year": 5, "day_of_month": 1,
                      "truncated": True},
           "--12": {"month_of_year": 12, "truncated": True},
           "---30": {"day_of_month": 30, "truncated": True},
           "98-354": {"year": 98, "day_of_year": 354, "truncated": True,
                      "truncated_property": "year_of_century"},
           "-034": {"day_of_year": 34, "truncated": True},
           "00-W03-1": {"year": 0, "week_of_year": 3, "day_of_week": 1,
                        "truncated": True,
                        "truncated_property": "year_of_century"},
           "99-W34": {"year": 99, "week_of_year": 34, "truncated": True,
                      "truncated_property": "year_of_century"},
           "-1-W02": {"year": 1, "week_of_year": 2,
                      "truncated": True,
                      "truncated_property": "year_of_decade"},
           "-W03-1": {"week_of_year": 3, "day_of_week": 1, "truncated": True},
           "-W32": {"week_of_year": 32, "truncated": True},
           "-W-1": {"day_of_week": 1, "truncated": True}}}}
    TEST_TIME_EXPRESSIONS = {"basic": {"complete": {
           "050102": {"hour_of_day": 5, "minute_of_hour": 1,
                      "second_of_minute": 2},
           "235902,345": {"hour_of_day": 23, "minute_of_hour": 59,
                          "second_of_minute": 2.345},
           "235902.345": {"hour_of_day": 23, "minute_of_hour": 59,
                          "second_of_minute": 2.345},
           "1201,4": {"hour_of_day": 12, "minute_of_hour": 1.4},
           "1201.4": {"hour_of_day": 12, "minute_of_hour": 1.4},
           "00,4356": {"hour_of_day": 0.4356},
           "00.4356": {"hour_of_day": 0.4356}},
                                  "reduced": {
           "0203": {"hour_of_day": 2, "minute_of_hour": 3},
           "17": {"hour_of_day": 17}},
                                  "truncated":{
           "-5612": {"minute_of_hour": 56, "second_of_minute": 12,
                     "truncated": True},
           "-12": {"minute_of_hour": 12, "truncated": True},
           "--45": {"second_of_minute": 45, "truncated": True},
           "-1234,45": {"minute_of_hour": 12, "second_of_minute": 34.45,
                        "truncated": True},
           "-1234.45": {"minute_of_hour": 12, "second_of_minute": 34.45,
                        "truncated": True},
           "-34,2": {"minute_of_hour": 34.2, "truncated": True},
           "-34.2": {"minute_of_hour": 34.2, "truncated": True},
           "--59,99": {"second_of_minute": 59.99, "truncated": True},
           "--59.99": {"second_of_minute": 59.99, "truncated": True}}},
                        "extended": {"complete": {
           "05:01:02": {"hour_of_day": 5, "minute_of_hour": 1,
                        "second_of_minute": 2},
           "23:59:02,345": {"hour_of_day": 23, "minute_of_hour": 59,
                            "second_of_minute": 2.345},
           "23:59:02.345": {"hour_of_day": 23, "minute_of_hour": 59,
                            "second_of_minute": 2.345},
           "12:01,4": {"hour_of_day": 12, "minute_of_hour": 1.4},
           "12:01.4": {"hour_of_day": 12, "minute_of_hour": 1.4},
           "00,4356": {"hour_of_day": 0.4356},
           "00.4356": {"hour_of_day": 0.4356}},
                                  "reduced": {
           "02:03": {"hour_of_day": 2, "minute_of_hour": 3},
           "17": {"hour_of_day": 17}},
                                  "truncated":{
           "-56:12": {"minute_of_hour": 56, "second_of_minute": 12,
                      "truncated": True},
           "-12": {"minute_of_hour": 12, "truncated": True},
           "--45": {"second_of_minute": 45, "truncated": True},
           "-12:34,45": {"minute_of_hour": 12, "second_of_minute": 34.45,
                         "truncated": True},
           "-12:34.45": {"minute_of_hour": 12, "second_of_minute": 34.45,
                         "truncated": True},
           "-34,2": {"minute_of_hour": 34.2, "truncated": True},
           "-34.2": {"minute_of_hour": 34.2, "truncated": True},
           "--59,99": {"second_of_minute": 59.99, "truncated": True},
           "--59.99": {"second_of_minute": 59.99, "truncated": True}}}}
    TEST_TIMEZONE_EXPRESSIONS = {"basic": {
           "Z": {"time_zone_utc": True},
           "+01": {"time_zone_hour": 1},
           "-05": {"time_zone_hour": -5},
           "+2301": {"time_zone_hour": 23, "time_zone_minute": 1},
           "-1230": {"time_zone_hour": -12, "time_zone_minute": 30}},
                            "extended": {
           "Z": {"time_zone_utc": True},
           "+01": {"time_zone_hour": 1},
           "-05": {"time_zone_hour": -5},
           "+23:01": {"time_zone_hour": 23, "time_zone_minute": 1},
           "-12:30": {"time_zone_hour": -12, "time_zone_minute": 30}}}

    def __init__(self, num_expanded_year_digits=2,
                 allow_truncated=False,
                 allow_only_basic=False,
                 assume_utc=False,
                 format_function=None):
        expanded_year_digit_regex = "\d" * num_expanded_year_digits
        self.expanded_year_digits = num_expanded_year_digits
        self.DATE_CHAR_REGEXES.append((u"Ϋ", "(?P<expanded_year>" +
                                             expanded_year_digit_regex + ")"))
        self.allow_truncated = allow_truncated
        self.allow_only_basic = allow_only_basic
        self.format_function = format_function
        self._generate_regexes()

    def _generate_regexes(self):
        """Generate combined date time strings."""
        date_map = self.DATE_EXPRESSIONS
        time_map = self.TIME_EXPRESSIONS
        timezone_map = self.TIMEZONE_EXPRESSIONS
        self._date_regex_map = {}
        self._time_regex_map = {}
        self._timezone_regex_map = {}
        format_ok_keys = ["basic", "extended"]
        if self.allow_only_basic:
            format_ok_keys = ["basic"]
        for format_type in format_ok_keys:
            self._date_regex_map.setdefault(format_type, {})
            self._time_regex_map.setdefault(format_type, {})
            self._timezone_regex_map.setdefault(format_type, [])
            for date_key in date_map[format_type].keys():
                self._date_regex_map[format_type].setdefault(date_key, [])
                regex_list = self._date_regex_map[format_type][date_key]
                for date_expr in self.get_expressions(
                                          date_map[format_type][date_key]):
                    date_regex = self.parse_date_expression_to_regex(
                                                            date_expr)
                    regex_list.append([re.compile(date_regex), date_expr])
            for time_key in time_map[format_type].keys():
                self._time_regex_map[format_type].setdefault(time_key, [])
                regex_list = self._time_regex_map[format_type][time_key]
                for time_expr in self.get_expressions(
                                          time_map[format_type][time_key]):
                    time_regex = self.parse_time_expression_to_regex(
                                                            time_expr)
                    regex_list.append([re.compile(time_regex), time_expr])
            for timezone_expr in self.get_expressions(
                                          timezone_map[format_type]):
                timezone_regex = self.parse_timezone_expression_to_regex(
                                                                timezone_expr)
                self._timezone_regex_map[format_type].append(
                               [re.compile(timezone_regex), timezone_expr])
                                          
    def get_expressions(self, text):
        """Yield valid expressions from text."""
        for line in text.splitlines():
            line_text = line.strip()
            if not line_text or line_text.startswith("#"):
                continue
            expr_text = line_text.split("#", 1)[0].strip()
            yield expr_text

    def parse_date_expression_to_regex(self, expression):
        """Construct regular expressions for the date."""
        for expr_regex, substitute in self.DATE_CHAR_REGEXES:
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse_time_expression_to_regex(self, expression):
        """Construct regular expressions for the time."""
        for expr_regex, substitute in self.TIME_CHAR_REGEXES:
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse_timezone_expression_to_regex(self, expression):
        """Construct regular expressions for the timezone."""
        for expr_regex, substitute in self.TIMEZONE_CHAR_REGEXES:
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse(self, timepoint_string):
        """Parse a user-supplied timepoint string."""
        date_time_timezone = timepoint_string.split(self.TIME_DESIGNATOR)
        if len(date_time_timezone) == 1:
            date = date_time_timezone[0]
            keys, date_info = self.get_date_info(date)
            time_info = {}
        else:
            date, time_timezone = date_time_timezone
            if not date and self.allow_truncated:
                keys = (None, "truncated")
                date_info = {"truncated": True}
            else:
                keys, date_info = self.get_date_info(date,
                                                     bad_types=["reduced"])
            format_key, type_key = keys
            bad_formats = []
            if format_key == "basic":
                bad_formats = ["extended"]
            if format_key == "extended":
                bad_formats = ["basic"]
            if type_key == "truncated":
                # Do not force basic/extended formatting for truncated dates.
                bad_formats = []
            bad_types = ["truncated"]
            if date_info.get("truncated"):
                bad_types = []
            if time_timezone.endswith("Z"):
                time, timezone = time_timezone[:-1], "Z"
            else:
                if "+" in time_timezone:
                    time, timezone = time_timezone.split("+")
                    timezone = "+" + timezone
                elif "-" in time_timezone:
                    time, timezone = time_timezone.rsplit("-", 1)
                    timezone = "-" + timezone
                    # Make sure this isn't just a truncated time.
                    try:
                        time_info = self.get_time_info(
                                             time,
                                             bad_formats=bad_formats,
                                             bad_types=bad_types)
                        timezone_info = self.get_timezone_info(
                                                timezone,
                                                bad_formats=bad_formats)
                    except TimeSyntaxError:
                        time = time_timezone
                        timezone = None
                else:
                    time = time_timezone
                    timezone = None
            if timezone is None:
                timezone_info = {}
            else:
                timezone_info = self.get_timezone_info(
                                                  timezone,
                                                  bad_formats=bad_formats)
                if timezone_info.pop("time_zone_sign", "+") == "-":
                    timezone_info["time_zone_hour"] = (
                             int(timezone_info["time_zone_hour"]) * -1)
                    if "time_zone_minute" in timezone_info:
                        timezone_info["time_zone_minute"] = (
                                 int(timezone_info["time_zone_minute"]) * -1)
            time_info = self.get_time_info(time, bad_formats=bad_formats,
                                           bad_types=bad_types)
            time_info.update(timezone_info)
        info = {}
        truncated_property = None
        if date_info.get("truncated"):
            if "year_of_decade" in date_info:
                truncated_property = "year_of_decade"
            if "year_of_century" in date_info:
                truncated_property = "year_of_century" 
        elif ("century" not in date_info and
              "year_of_century" in date_info):
            truncated_property = "year_of_century"
            date_info["truncated"] = True
        year = int(date_info.get("year", 0))
        if "year_of_decade" in date_info:
            year += int(date_info.pop("year_of_decade"))
            truncated_property = "year_of_decade"
        year += int(date_info.pop("year_of_century", 0))
        year += 100 * int(date_info.pop("century", 0))
        expanded_year = date_info.pop("expanded_year", 0)
        if expanded_year:
            date_info["expanded_year_digits"] = self.expanded_year_digits
        year += 10000 * int(expanded_year)
        if date_info.pop("year_sign", "+") == "-":
            year *= -1
        date_info["year"] = year
        for key, value in date_info.items():
            try:
                date_info[key] = int(value)
            except (TypeError, ValueError):
                pass
        info.update(date_info)
        for key, value in time_info.items():
            if key.endswith("_decimal"):
                value = "0." + value
            try:
                value = float(value)
            except (IOError, ValueError) as e:
                pass
            if key == "time_zone_utc" and value == "Z":
                value = True
            if key == "year_sign":
                if value == "+":
                    value = 1
                else:
                    value = -1
            time_info[key] = value
        info.update(time_info)
        if info.pop("truncated", False):
            info["truncated"] = True
        if truncated_property is not None:
            info["truncated_property"] = truncated_property
        if self.format_function is not None:
            info.update({"format_function": self.format_function})
        return TimePoint(**info)

    def get_date_info(self, date_string, bad_types=None):
        """Return the format and properties from a date string."""
        type_keys = ["complete", "truncated", "reduced"]
        if bad_types is not None:
            for type_key in bad_types:
                type_keys.remove(type_key)
        if not self.allow_truncated and "truncated" in type_keys:
            type_keys.remove("truncated")
        for format_key, type_regex_map in self._date_regex_map.items():
            for type_key in type_keys:
                regex_list = type_regex_map[type_key]
                for regex, expr in regex_list:
                    result = regex.match(date_string)
                    if result:
                        return (format_key, type_key), result.groupdict()
        raise TimeSyntaxError(
                    "Not a valid ISO 8601 date representation: %s" %
                    date_string)

    def get_time_info(self, time_string, bad_formats=None, bad_types=None):
        """Return the properties from a time string."""
        if bad_formats is None:
            bad_formats = []
        if bad_types is None:
            bad_types = []
        for format_key, type_regex_map in self._time_regex_map.items():
            if format_key in bad_formats:
                continue
            for type_key, regex_list in type_regex_map.items():
                if type_key in bad_types:
                    continue
                for regex, expr in regex_list:
                    result = regex.match(time_string)
                    if result:
                        return result.groupdict()
        raise TimeSyntaxError(
                    "Not a valid ISO 8601 time representation: %s" %
                    time_string)

    def get_timezone_info(self, timezone_string, bad_formats=None):
        """Return the properties from a timezone string."""
        if bad_formats is None:
            bad_formats = []
        for format_key, regex_list in self._timezone_regex_map.items():
            if format_key in bad_formats:
                continue
            for regex, expr in regex_list:
                result = regex.match(timezone_string)
                if result:
                    return result.groupdict()
        raise TimeSyntaxError(
                    "Not a valid ISO 8601 timezone representation: %s" %
                    timezone_string)

    def get_tests(self):
        """Return self-tests as (str, TimePoint kwargs) tuples."""
        format_ok_keys = ["basic", "extended"]
        if self.allow_only_basic:
            format_ok_keys = ["basic"]  
        date_combo_ok_keys = ["complete"]
        if self.allow_truncated:
            date_combo_ok_keys = ["complete", "truncated"]
        time_combo_ok_keys = ["complete", "reduced"]
        test_date_map = self.TEST_DATE_EXPRESSIONS
        test_time_map = self.TEST_TIME_EXPRESSIONS
        test_timezone_map = self.TEST_TIMEZONE_EXPRESSIONS
        for format_type in format_ok_keys:
            date_format_tests = test_date_map[format_type]
            time_format_tests = test_time_map[format_type]
            timezone_format_tests = test_timezone_map[format_type]
            for date_key in date_format_tests:
                if not self.allow_truncated and date_key == "truncated":
                    continue
                for date_expr, info in date_format_tests[date_key].items():
                    yield date_expr, info
            for date_key in date_combo_ok_keys:
                date_tests = copy.deepcopy(date_format_tests[date_key])
                # Add a blank date for time-only testing.
                for date_expr, info in date_tests.items():
                    for time_key in time_combo_ok_keys:
                        time_items = time_format_tests[time_key].items()
                        for time_expr, time_info in time_items:
                            combo_expr = (date_expr + self.TIME_DESIGNATOR +
                                          time_expr)
                            combo_info = {}
                            for key, value in info.items() + time_info.items():
                                combo_info[key] = value
                            yield combo_expr, combo_info
                            timezone_items = timezone_format_tests.items()
                            for timezone_expr, timezone_info in timezone_items:
                                tz_expr = combo_expr + timezone_expr
                                tz_info = {}
                                for key, value in (combo_info.items() +
                                                   timezone_info.items()):
                                    tz_info[key] = value
                                yield tz_expr, tz_info
            if not self.allow_truncated:
                continue
            for time_key in time_format_tests:
                time_tests = time_format_tests[time_key]
                for time_expr, time_info in time_tests.items():
                    combo_expr = self.TIME_DESIGNATOR + time_expr
                    # Add truncated (no date).
                    combo_info = {"truncated": True}
                    for key, value in time_info.items():
                        combo_info[key] = value
                    yield combo_expr, combo_info
                    timezone_items = timezone_format_tests.items()
                    for timezone_expr, timezone_info in timezone_items:
                        tz_expr = combo_expr + timezone_expr
                        tz_info = {}
                        for key, value in (combo_info.items() +
                                           timezone_info.items()):
                            tz_info[key] = value
                        yield tz_expr, tz_info
                        

class TimeIntervalParser(object):

    """Parser for ISO 8601 Durations (time intervals)."""
             
    INTERVAL_REGEXES = [
             re.compile(r"""^P(?:(?P<years>\d+)Y)?
                              (?:(?P<months>\d+)M)?
                              (?:(?P<days>\d+)D)?$""", re.X),
             re.compile(r"""^P(?:(?P<years>\d+)Y)?
                              (?:(?P<months>\d+)M)?
                              (?:(?P<days>\d+)D)?
                              T(?:(?P<hours>\d.*)H)?
                               (?:(?P<minutes>\d.*)M)?
                               (?:(?P<seconds>\d.*)S)?$""", re.X),
             re.compile(r"""^P(?P<weeks>\d+)W$""", re.X)]

    def parse(self, expression):
        """Parse an ISO duration expression into a TimeInterval instance."""
        for rec_regex in self.INTERVAL_REGEXES:
            result = rec_regex.search(expression)
            if not result:
                continue
            result_map = result.groupdict()
            for key, value in result_map.items():
                if value is None:
                    result_map.pop(key)
                    continue
                if key in ["years", "months", "days", "weeks"]:
                    value = int(value)
                else:
                    if "," in value:
                        value = value.replace(",", ".")
                    value = float(value)
                result_map[key] = value
            return TimeInterval(**result_map)
        raise TimeSyntaxError("Not an ISO 8601 duration representation: %s" %
                              expression)

    def get_tests(self):
        """Yield self-tests as (input_string, output_string) tuples."""

        self.TEST_EXPRESSIONS = {
                "P3Y": str(TimeInterval(years=3)),
                "P90Y": str(TimeInterval(years=90)),
                "P1Y2M": str(TimeInterval(years=1, months=2)),
                "P20Y2M": str(TimeInterval(years=20, months=2)),
                "P2M": str(TimeInterval(months=2)),
                "P52M": str(TimeInterval(months=52)),
                "P20Y10M2D": str(TimeInterval(years=20, months=10, days=2)),
                "P1Y3D": str(TimeInterval(years=1, days=3)),
                "P4M1D": str(TimeInterval(months=4, days=1)),
                "P3Y404D": str(TimeInterval(years=3, days=404)),
                "P30Y2D": str(TimeInterval(years=30, days=2)),
                "PT6H": str(TimeInterval(hours=6)),
                "PT1034H": str(TimeInterval(hours=1034)),
                "P3YT4H2M": str(TimeInterval(years=3, hours=4, minutes=2)),
                "P30Y2DT10S": str(TimeInterval(years=30, days=2, seconds=10)),
                "PT2S": str(TimeInterval(seconds=2)),
                "PT2.5S": str(TimeInterval(seconds=2.5)),
                "PT2,5S": str(TimeInterval(seconds=2.5)),
                "PT5.5023H": str(TimeInterval(hours=5.5023)),
                "PT5,5023H": str(TimeInterval(hours=5.5023)),
                "P5W": str(TimeInterval(weeks=5)),
                "P100W": str(TimeInterval(weeks=100))}
        for expression, ctrl_result in self.TEST_EXPRESSIONS.items():
            yield expression, ctrl_result


class TimeSyntaxError(ValueError):

    """An error denoting invalid input syntax."""


class TimeRecurrence(object):

    """Represent a recurring time interval."""

    TEST_EXPRESSIONS = [
            ("R3/1001-W01-1T00:00:00Z/1002-W52-6T00:00:00-05:30",
             ["1001-W01-1T00:00:00Z", "1001-W53-3T14:45:00Z",
              "1002-W52-6T05:30:00Z" ]), 
            ("R3/P700D/1957-W01-1T06,5Z",
             ["1953-W10-1T06,5Z", "1955-W05-1T06,5Z", "1957-W01-1T06,5Z"]),
            ("R3/P5DT2,5S/1001-W11-1T00:30:02,5-02:00",
             ["1001-W09-5T00:29:57,5-02:00", "1001-W10-3T00:30:00-02:00",
              "1001-W11-1T00:30:02,5-02:00"]),
            ("R/+000001W457T060000Z/P4M1D",
             ["+000001-W45-7T06:00:00Z", "+000002-W11-2T06:00:00Z",
              "+000002-W28-6T06:00:00Z"]),
            ("R/P4M1DT6M/+002302-002T06:00:00-00:30",
             ["+002302-002T06:00:00-00:30", "+002301-244T05:54:00-00:30",
              "+002301-120T05:48:00-00:30"]),
            ("R/P30Y2DT15H/-099994-02-12T17:00:00-02:30",
             ["-099994-02-12T17:00:00-02:30", "-100024-02-10T02:00:00-02:30",
              "-100054-02-07T11:00:00-02:30"]),
            ("R/-100024-02-10T17:00:00-12:30/PT5.5H",
             ["-100024-02-10T17:00:00-12:30", "-100024-02-10T22,5-12:30",
              "-100024-02-11T04:00:00-12:30"])]

    def __init__(self, repetitions=None, start_point=None,
                 interval=None, end_point=None, min_point=None,
                 max_point=None):
        self.repetitions = repetitions
        self.start_point = start_point
        self.interval = interval
        self.end_point = end_point
        self.min_point = min_point
        self.max_point = max_point
        self.format_number = None
        if self.interval is None:
            # First form.
            self.format_number = 1
            start_year, start_days = self.start_point.get_ordinal_date()
            start_seconds = self.start_point.get_second_of_day()
            self.end_point.set_time_zone(self.start_point.time_zone)
            end_year, end_days = self.end_point.get_ordinal_date()
            end_seconds = self.end_point.get_second_of_day()
            diff_days = end_days - start_days
            while end_year != start_year:
                diff_days += get_days_in_year(start_year)
                start_year += 1
            diff_seconds = end_seconds - start_seconds
            while diff_seconds < 0:
                diff_days -= 1
                diff_seconds += 86400
            while diff_seconds >= 86400:
                diff_days += 1
                diff_seconds -= 86400
            if self.repetitions == 1:
                self.interval = TimeInterval(years=0)
            else:
                diff_days_float = diff_days / float(
                                       self.repetitions - 1)
                diff_seconds_float = diff_seconds / float(
                                       self.repetitions - 1)
                diff_days = int(diff_days_float)
                diff_seconds_float += (diff_days_float - diff_days) * 86400
                self.interval = TimeInterval(days=diff_days,
                                             seconds=diff_seconds_float)
        elif self.end_point is None:
            # Third form.
            self.format_number = 3
            if self.repetitions is not None:
                point = self.start_point
                for i in range(self.repetitions - 1):
                    point += self.interval
                self.end_point = point
        elif self.start_point is None:
            # Fourth form.
            self.format_number = 4
            if self.repetitions is not None:
                point = self.end_point
                for i in range(self.repetitions - 1):
                    point -= self.interval
                self.start_point = point
        else:
            raise ValueError("Unsupported or invalid recurrence information.")

    def __iter__(self):
        if self.start_point is None:
            point = self.end_point
            in_reverse = True
        else:
            point = self.start_point
            in_reverse = False
        
        if self.repetitions == 1 or not self.interval:
            if self.get_is_valid(point):
                yield point
            point = None

        while point is not None:
            if self.get_is_valid(point):
                yield point
            else:
                break
            if in_reverse:
                point = self.get_prev(point)
            else:
                point = self.get_next(point)

    def get_is_valid(self, timepoint):
        """Return whether the timepoint is within this recurrence series."""
        if timepoint is None:
            return False
        if self.start_point is not None and timepoint < self.start_point:
            return False
        if self.min_point is not None and timepoint < self.min_point:
            return False
        if self.max_point is not None and timepoint > self.max_point:
            return False
        if self.end_point is not None and timepoint > self.end_point:
            return False
        return True

    def get_next(self, timepoint):
        """Return the next timepoint after this timepoint, or None."""
        next_timepoint = timepoint + self.interval
        if self.get_is_valid(next_timepoint):
            return next_timepoint
        if (self.format_number == 1 and next_timepoint > self.end_point):
            diff = next_timepoint - self.end_point
            if 2 * diff < self.interval and self.get_is_valid(self.end_point):
                return self.end_point
        return None

    def get_prev(self, timepoint):
        """Return the previous timepoint before this timepoint, or None."""
        prev_timepoint = timepoint - self.interval
        if self.get_is_valid(prev_timepoint):
            return prev_timepoint
        return None

    def __str__(self):
        if self.repetitions is None:
            prefix = "R/"
        else:
            prefix = "R" + str(self.repetitions) + "/"
        if self.format_number == 1:
            return prefix + str(self.start_point) + "/" + str(self.end_point)
        elif self.format_number == 3:
            return prefix + str(self.start_point) + "/" + str(self.interval)
        elif self.format_number == 4:
            return prefix + str(self.interval) + "/" + str(self.end_point)
        return "R/?/?"

    def get_tests(self):
        """Return a series of self-tests."""
        for recur_expression, result_points in self.TEST_EXPRESSIONS:
            yield recur_expression, result_points


class TimeInterval(object):

    """Represent a duration or period of time."""

    def __init__(self, years=0, months=0, weeks=0, days=0,
                 hours=0.0, minutes=0.0, seconds=0.0):
        self.years = years
        self.months = months
        self.weeks = None
        self.days = days
        if weeks is not None:
            if days is None:
                self.days = 7 * weeks
            else:
                self.days += 7 * weeks
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        if (not self.years and not self.months and not self.hours and
            not self.minutes and not self.seconds and
            weeks and not days):
            self.weeks = self.days / 7
            self.years, self.months, self.days = (None, None, None)
            self.hours, self.minutes, self.seconds = (None, None, None)

    def copy(self):
        """Return an unlinked copy of this instance."""
        return TimeInterval(years=self.years, months=self.months,
                            weeks=self.weeks,
                            days=self.days, hours=self.hours,
                            minutes=self.minutes, seconds=self.seconds)

    def get_days_and_seconds(self):
        """Return a roughly-converted duration in days and seconds.

        This is not particularly nice, as years have to be assumed
        equal to 365 days, months to 30, in order to work (no context
        can be supplied). This code needs improving.
        
        Seconds are returned in the range 0 <= seconds < 86400, which
        means that a TimeInterval which has self.seconds = 86500 will
        return 1 day, 100 seconds or (1, 100) from this method.

        """
        # TODO: Implement error calculation for the below quantities.
        new = self.copy()
        new.to_days()
        new_days = new.years * 365 + new.months * 30 + new.days
        new_seconds = new.hours * 3600 + new.minutes * 60 + new.seconds
        while new_seconds >= 86400:
            new_days += 1
            new_seconds -= 86400
        while new_seconds < 0:
            new_days -= 1
            new_seconds += 86400
        return new_days, new_seconds

    def get_is_in_weeks(self):
        """Return whether we are in week representation."""
        return (self.weeks is not None)

    def to_days(self):
        """Convert to day representation rather than weeks."""
        if self.get_is_in_weeks():
            for attribute in [self.years, self.months, self.hours,
                              self.minutes, self.seconds]:
                if attribute is None:
                    attribute = 0
            self.days = self.weeks * 7
            self.weeks = None

    def to_weeks(self):
        if not self.get_is_in_weeks():
            self.weeks = self.days / 7
            self.years, self.months, self.days = (None, None, None)
            self.hours, self.minutes, self.seconds = (None, None, None)

    def __add__(self, other):
        new = self.copy()
        if isinstance(other, TimeInterval):
            if new.get_is_in_weeks():
                if other.get_is_in_weeks():
                    new.weeks += other.weeks
                    return new
                new.to_days()
            elif other.get_is_in_weeks():
                other = other.copy().to_days()
            new.years += other.years
            new.months += other.months
            new.days += other.days
            new.hours += other.hours
            new.minutes += other.minutes
            new.seconds += other.seconds
            return new
        if isinstance(other, TimePoint):
            return other + new
        raise TypeError(
                  "Invalid type for addition: " +
                  "'%s' should be TimeInterval or TimePoint." %
                  type(other).__name__)

    def __sub__(self, other):
        new = self.copy()
        if isinstance(other, TimeInterval):
            if new.get_is_in_weeks():
                if other.get_is_in_weeks():
                    new.weeks -= other.weeks
                    return new
                new.to_days()
            elif other.get_is_in_weeks():
                other = other.copy().to_days()
            new.years -= other.years
            new.months -= other.months
            new.days -= other.days
            new.hours -= other.hours
            new.minutes -= other.minutes
            new.seconds -= other.seconds
            return new
        if isinstance(other, TimePoint):
            return other - new
        raise TypeError(
                  "Invalid type for subtraction: " +
                  "'%s' should be TimeInterval or TimePoint." %
                  type(other).__name__)

    def __mul__(self, other):
        # TODO: support float multiplication?
        new = self.copy()
        if not isinstance(other, int):
            raise TypeError(
                  "Invalid type for multiplication: " +
                  "'%s' should be integer." %
                  type(other).__name__)
        if self.get_is_in_weeks():
            new.weeks *= other
            return new
        new.years *= other
        new.months *= other
        new.days *= other
        new.hours *= other
        new.minutes *= other
        new.seconds *= other
        return new

    def __rmul__(self, other):
        return self.__mul__(other)

    def __floordiv__(self, other):
        # TODO: support float division?
        new = self.copy()
        if not isinstance(other, int):
            raise TypeError(
                  "Invalid type for division: " +
                  "'%s' should be integer." %
                  type(other).__name__)
        if self.get_is_in_weeks():
            new.weeks //= other
            return new
        new.years //= other
        new.months //= other
        new.days //= other
        new.hours //= other
        new.minutes //= other
        new.seconds //= other

    def __cmp__(self, other):
        if not isinstance(other, TimeInterval):
            raise TypeError(
                  "Invalid type for comparison: " +
                  "'%s' should be TimeInterval." %
                  type(other).__name__)
        my_data = self.get_days_and_seconds()
        other_data = other.get_days_and_seconds()
        return cmp(my_data, other_data)

    def __nonzero__(self):
        for attr in ["years", "months", "weeks", "days", "hours",
                     "minutes", "seconds"]:
            if getattr(self, attr, None):
                return True
        return False

    def __str__(self):
        start_string = "P"
        date_string = ""
        time_string = ""
        if self.get_is_in_weeks():
            return (start_string + str(self.weeks) + "W").replace(".", ",")
        if self.years:
            date_string += str(self.years) + "Y"
        if self.months:
            date_string += str(self.months) + "M"
        if self.days:
            date_string += str(self.days) + "D"
        if self.hours:
            if int(self.hours) == self.hours:
                time_string += str(int(self.hours)) + "H"
            else:
                time_string += ("%f" % self.hours).rstrip("0") + "H"
        if self.minutes:
            if int(self.minutes) == self.minutes:
                time_string += str(int(self.minutes)) + "M"
            else:
                time_string += ("%f" % self.minutes).rstrip("0") + "M"
        if self.seconds:
            if int(self.seconds) == self.seconds:
                time_string += str(int(self.seconds)) + "S"
            else:
                time_string += ("%f" % self.seconds).rstrip("0") + "S"
        if time_string:
            time_string = "T" + time_string
        elif not date_string:
            # Zero duration.
            date_string = "0Y"
        total_string = start_string + date_string + time_string
        return total_string.replace(".", ",")


class TimeZone(TimeInterval):

    """Represent a time zone offset."""

    def __init__(self, *args, **kwargs):
        self.unknown = kwargs.pop("unknown", False)
        super(TimeZone, self).__init__(*args, **kwargs)

    def copy(self):
        """Return an unlinked copy of this instance."""
        return TimeZone(hours=self.hours, minutes=self.minutes,
                        unknown=self.unknown)

    def __str__(self):
        if self.unknown:
            return ""
        if self.hours == 0 and self.minutes == 0:
            return "Z"
        else:
            time_string = "+%02d:%02d"
            if self.hours < 0 or (self.hours == 0 and self.minutes < 0):
                time_string = "-%02d:%02d"
            return time_string % (abs(self.hours), abs(self.minutes))


class TimePoint(object):

    """Represent an instant in time."""

    def __init__(self, **kwargs):
        self.format_function = kwargs.get("format_function")
        self.expanded_year_digits = kwargs.get("expanded_year_digits", 0)
        self.truncated = kwargs.get("truncated", False)
        self.truncated_property = kwargs.get("truncated_property")
        self.year = kwargs.get("year")
        self.month_of_year = kwargs.get("month_of_year")
        self.day_of_year = kwargs.get("day_of_year")
        self.day_of_month = kwargs.get("day_of_month")
        self.day_of_week = kwargs.get("day_of_week")
        self.week_of_year = kwargs.get("week_of_year")
        if self.truncated:
            time_default = None
        else:
            time_default = 0
        self.hour_of_day = kwargs.get("hour_of_day", time_default)
        if "hour_of_day_decimal" in kwargs:
            if self.hour_of_day is None:
                raise TimePointInputError(
                          "Invalid input: hour decimal points - but not hours")
            self.hour_of_day += kwargs.get("hour_of_day_decimal")
            if "minute_of_hour" in kwargs:
                raise TimePointInputError(
                          "Invalid input: minutes - already have hour decimals")
            if "second_of_minute" in kwargs:
                raise TimePointInputError(
                          "Invalid input: seconds - already have hour decimals")
        if "minute_of_hour_decimal" in kwargs:
            if "minute_of_hour" not in kwargs:
                raise TimePointInputError(
                          "Invalid input: minute decimal points - but not minutes")
            self.minute_of_hour = kwargs["minute_of_hour"]
            self.minute_of_hour += kwargs["minute_of_hour_decimal"]
            if "second_of_minute" in kwargs:
                raise TimePointInputError(
                          "Invalid input: seconds - already have minute decimals")
        else:
            self.minute_of_hour = kwargs.get("minute_of_hour", time_default)
        if "second_of_minute_decimal" in kwargs:
            if "second_of_minute" not in kwargs:
                raise TimePointInputError(
                          "Invalid input: second decimal points - but not seconds")
            self.second_of_minute = kwargs["second_of_minute"]
            self.second_of_minute += kwargs["second_of_minute_decimal"]
        else:
            self.second_of_minute = kwargs.get("second_of_minute", time_default)
        self.time_zone = TimeZone()
        has_unknown_tz = True
        if "time_zone_hour" in kwargs:
            has_unknown_tz = False
            self.time_zone.hours = kwargs.get("time_zone_hour")
        if "time_zone_minute" in kwargs:
            has_unknown_tz = False
            self.time_zone.minutes = kwargs.get("time_zone_minute")
        has_unknown_tz = self.truncated and has_unknown_tz
        self.time_zone.unknown = has_unknown_tz
        if not self.truncated:
            # Reduced precision date - e.g. 1970 - assume Jan 1, etc.
            if (self.month_of_year is None and self.week_of_year is None and
                self.day_of_year is None):
                self.month_of_year = 1
            if self.month_of_year is not None and self.day_of_month is None:
                self.day_of_month = 1
            if self.week_of_year is not None and self.day_of_week is None:
                self.day_of_week = 1

    def get_is_calendar_date(self):
        """Return whether this is in years, month-of-year, day-of-month."""
        return self.month_of_year is not None

    def get_is_ordinal_date(self):
        """Return whether this is in years, day-of-the year format."""
        return self.day_of_year is not None

    def get_is_week_date(self):
        """Return whether this is in years, week-of-year, day-of-week."""
        return self.week_of_year is not None

    def get_calendar_date(self):
        """Return the year, month-of-year and day-of-month for this date."""
        if self.get_is_calendar_date():
            return self.year, self.month_of_year, self.day_of_month
        if self.get_is_ordinal_date():
            return get_calendar_date_from_ordinal_date(self.year,
                                                       self.day_of_year)
        if self.get_is_week_date():
            return get_calendar_date_from_week_date(self.year,
                                                    self.week_of_year,
                                                    self.day_of_week)

    def get_hour_minute_second(self):
        """Return the time of day expressed in hours, minutes, seconds."""
        hour_of_day = self.hour_of_day
        minute_of_hour = self.minute_of_hour
        second_of_minute = self.second_of_minute
        if second_of_minute is None:
            if minute_of_hour is None:
                hour_decimals = hour_of_day - int(hour_of_day)
                hour_of_day = float(int(hour_of_day))
                minute_of_hour = 60 * hour_decimals
            minute_decimals = minute_of_hour - int(minute_of_hour)
            minute_of_hour = float(int(minute_of_hour))
            second_of_minute = 60 * minute_decimals
        return hour_of_day, minute_of_hour, second_of_minute

    def get_ordinal_date(self):
        """Return the year, day-of-year for this date."""
        if self.get_is_calendar_date():
            return get_ordinal_date_from_calendar_date(self.year,
                                                       self.month_of_year,
                                                       self.day_of_month)
        if self.get_is_ordinal_date():
            return self.year, self.day_of_year
        if self.get_is_week_date():
            return get_ordinal_date_from_week_date(self.year,
                                                   self.week_of_year,
                                                   self.day_of_week)

    def get_second_of_day(self):
        """Return the seconds elapsed since the start of the day."""
        second_of_day = 0
        if self.second_of_minute is not None:
            second_of_day += self.second_of_minute
        if self.minute_of_hour is not None:
            second_of_day += self.minute_of_hour * 60
        second_of_day += self.hour_of_day * 3600
        return second_of_day

    def get_time_zone(self):
        """Return the time_zone offset from UTC as a duration."""
        return self.time_zone

    def get_time_zone_utc(self):
        """Return whether the time zone is explicitly in UTC."""
        if self.time_zone.unknown:
            return False
        return self.time_zone.hours == 0 and self.time_zone.minutes == 0

    def get_week_date(self):
        """Return the year, week-of-year, day-of-week for this date."""
        if self.get_is_calendar_date():
            return get_week_date_from_calendar_date(self.year,
                                                    self.month_of_year,
                                                    self.day_of_month)
        if self.get_is_ordinal_date():
            return get_week_date_from_ordinal_date(self.year,
                                                   self.day_of_year)
        if self.get_is_week_date():
            return self.year, self.week_of_year, self.day_of_week

    def apply_time_zone_offset(self, offset):
        """Apply a time zone shift represented by a TimeInterval."""
        if offset.minutes:
            if self.minute_of_hour is None:
                self.hour_of_day += offset.minutes / 60.0
            else:
                self.minute_of_hour += offset.minutes
            self._tick_over()
        if offset.hours:
            self.hour_of_day += offset.hours
            self._tick_over()

    def get_time_zone_offset(self, other):
        """Get the difference in hours and minutes between time zones."""
        if other.get_time_zone().unknown or self.get_time_zone().unknown:
            return TimeInterval()
        return other.get_time_zone() - self.get_time_zone()

    def set_time_zone(self, dest_time_zone):
        """Adjust to the new time zone.

        dest_time_zone should be a TimeZone instance expressing difference
        from UTC, if any.

        """
        if dest_time_zone.unknown:
            return
        self.apply_time_zone_offset(dest_time_zone - self.get_time_zone())
        self.time_zone = dest_time_zone 

    def to_calendar_date(self):
        """Reformat the date in years, month-of-year, day-of-month."""
        year, month, day = self.get_calendar_date()
        self.year, self.month_of_year, self.day_of_month = year, month, day
        self.day_of_year = None
        self.week_of_year = None
        self.day_of_week = None
        return self

    def to_hour_minute_second(self):
        """Expand time fractions into hours, minutes, seconds."""
        hour, minute, second = self.get_hour_minute_second()
        self.hour_of_day = hour
        self.minute_of_hour = minute
        self.second_of_day = second

    def to_week_date(self):
        """Reformat the date in years, week-of-year, day-of-week."""
        self.year, self.week_of_year, self.day_of_week = self.get_week_date()
        self.day_of_year = None
        self.month_of_year = None
        self.day_of_month = None
        return self

    def to_ordinal_date(self):
        """Reformat the date in years and day-of-the-year."""
        self.year, self.day_of_year = self.get_ordinal_date()
        self.month_of_year = None
        self.day_of_month = None
        self.week_of_year = None
        self.day_of_week = None
        return self

    def get_largest_truncated_property_name(self):
        """Return the largest unit in a truncated representation."""
        if not self.truncated:
            return None
        prop_dict = self.get_truncated_properties()
        for attr in ["year_of_century", "year_of_decade", "month_of_year",
                     "week_of_year", "day_of_year", "day_of_month",
                     "day_of_week", "hour_of_day", "minute_of_hour",
                     "second_of_minute"]:
            if attr in prop_dict:
                return attr
        return None

    def get_truncated_properties(self):
        """Return a map of properties if this is a truncated representation."""
        if not self.truncated:
            return None
        props = {}
        if self.truncated_property == "year_of_decade":
            props.update({"year_of_decade": self.year % 10})
        if self.truncated_property == "year_of_century":
            props.update({"year_of_century": self.year % 100})
        for attr in ["month_of_year", "week_of_year", "day_of_year",
                     "day_of_month", "day_of_week", "hour_of_day",
                     "minute_of_hour", "second_of_minute"]:
            value = getattr(self, attr)
            if value is not None:
                props.update({attr: value})
        return props

    def add_truncated(self, year_of_century=None, year_of_decade=None,
                      month_of_year=None, week_of_year=None, day_of_year=None,
                      day_of_month=None, day_of_week=None, hour_of_day=None,
                      minute_of_hour=None, second_of_minute=None):
        """Combine this TimePoint with truncated time properties."""
        new = self.copy()
        if hour_of_day is not None and minute_of_hour is None:
            minute_of_hour = 0
        if ((hour_of_day is not None or minute_of_hour is not None) and
            second_of_minute is None):
            second_of_minute = 0
        if second_of_minute is not None or minute_of_hour is not None:
            new.to_hour_minute_second()
        if second_of_minute is not None:
            while new.second_of_minute != second_of_minute:
                new.second_of_minute += 1.0
                new._tick_over()
        if minute_of_hour is not None:
            while new.minute_of_hour != minute_of_hour:
                new.minute_of_hour += 1.0
                new._tick_over()
        if hour_of_day is not None:
            while new.hour_of_day != hour_of_day:
                new.hour_of_day += 1.0
                new._tick_over()
        if day_of_week is not None:
            new.to_week_date()
            while new.day_of_week != day_of_week:
                new.day_of_week += 1
                new._tick_over()
        if day_of_month is not None:
            new.to_calendar_date()
            while new.day_of_month != day_of_month:
                new.day_of_month += 1
                new._tick_over()
        if day_of_year is not None:
            new.to_ordinal_date()
            while new.day_of_year != day_of_year:
                new.day_of_year += 1
                new._tick_over()
        if week_of_year is not None:
            new.to_week_date()
            while new.week_of_year != week_of_year:
                new.week_of_year += 1
                new._tick_over()
        if month_of_year is not None:
            new.to_calendar_date()
            while new.month_of_year != month_of_year:
                new.month_of_year += 1
                new._tick_over()
        if year_of_decade is not None:
            new.to_calendar_date()
            new_year_of_decade = new.year % 10
            while new_year_of_decade != year_of_decade:
                new.year += 1
                new_year_of_decade = new.year % 10
        if year_of_century is not None:
            new.to_calendar_date()
            new_year_of_century = new.year % 100
            while new_year_of_century != year_of_century:
                new.year += 1
                new_year_of_century = new.year % 100
        return new

    def __add__(self, other, no_copy=False):
        if isinstance(other, TimePoint):
            if self.truncated and not other.truncated:
                new = self.copy()
                new_other = other.copy()
                prev_time_zone = new_other.get_time_zone()
                new_other.set_time_zone(new.get_time_zone())
                new_other = new_other.add_truncated(
                                  **new.get_truncated_properties())
                new_other.set_time_zone(prev_time_zone)
                return new_other
            if other.truncated and not self.truncated:
                return other + self
        if not isinstance(other, TimeInterval):
            raise TypeError(
                      "Invalid addition: can only add TimeInterval or "
                      "truncated TimePoint to TimePoint.")
        duration = other
        if duration.get_is_in_weeks():
            duration = other.copy()
            duration.to_days()
        if no_copy:
            new = self
        else:
            new = self.copy()
        if duration.seconds:
            if new.second_of_minute is None:
                if new.minute_of_hour is None:
                    new.hour_of_day += duration.seconds / 3600.0
                else:
                    new.minute_of_hour += duration.seconds / 60.0
            else:
                new.second_of_minute += duration.seconds
            new._tick_over()
        if duration.minutes:
            if new.minute_of_hour is None:
                new.hour_of_day += duration.minutes / 3600.0
            else:
                new.minute_of_hour += duration.minutes
            new._tick_over()
        if duration.hours:
            new.hour_of_day += duration.hours
            new._tick_over()
        if duration.days:
            if new.get_is_calendar_date():
                new.day_of_month += duration.days
            elif new.get_is_ordinal_date():
                new.day_of_year += duration.days
            else:
                new.day_of_week += duration.days
            new._tick_over()
        if duration.months:
            # This is the dangerous one...
            new._add_months(duration.months)
        if duration.years:
            new.year += duration.years
            if new.get_is_calendar_date():
                month_index = (new.month_of_year - 1) % 12
                if get_is_leap_year(new.year):
                    max_day_in_new_month = DAYS_OF_MONTHS_LEAP[month_index]
                else:
                    max_day_in_new_month = DAYS_OF_MONTHS[month_index]
                if new.day_of_month > max_day_in_new_month:
                    # For example, when Feb 29 - 1 year = Feb 28.
                    new.day_of_month = max_day_in_new_month
            elif new.get_is_ordinal_date():
                max_days_in_year = get_days_in_year(new.year)
                if max_days_in_year > new.day_of_year:
                    new.day_of_year = max_days_in_year
            elif new.get_is_week_date():
                max_weeks_in_year = get_weeks_in_year(new.year)
                if max_weeks_in_year > new.week_of_year:
                    new.week_of_year = max_weeks_in_year
        return new

    def copy(self):
        """Copy this TimePoint without leaving references."""
        dummy_timepoint = TimePoint()
        for attr in ["expanded_year_digits", "year", "month_of_year",
                     "day_of_year", "day_of_month", "day_of_week",
                     "week_of_year", "hour_of_day", "minute_of_hour",
                     "second_of_minute", "truncated", "truncated_property",
                     "format_function"]:
            setattr(dummy_timepoint, attr, getattr(self, attr))
        dummy_timepoint.time_zone = self.time_zone.copy()
        return dummy_timepoint

    def __cmp__(self, other):
        if not isinstance(other, TimePoint):
            raise TypeError(
                      "Invalid comparison type '%s' - should be TimePoint." %
                      type(other).__name__)
        other = other.copy()
        other.set_time_zone(self.get_time_zone())
        if self.get_is_calendar_date():
            my_date = self.get_calendar_date()
            other_date = other.get_calendar_date()
        else:
            my_date = self.get_ordinal_date()
            other_date = other.get_ordinal_date()
        my_datetime = list(my_date) + [self.get_second_of_day()]
        other_datetime = list(other_date) + [other.get_second_of_day()]
        return cmp(my_datetime, other_datetime)

    def __sub__(self, other):
        if isinstance(other, TimePoint):
            other = other.copy()
            other.set_time_zone(self.get_time_zone())
            my_year, my_day_of_year = self.get_ordinal_date()
            other_year, other_day_of_year = other.get_ordinal_date()
            diff_year = my_year - other_year
            diff_day = my_day_of_year - other_day_of_year
            if my_year > other_year:
                for year in range(other_year, my_year):
                    diff_day += get_days_in_year(year)
            else:
                for year in range(my_year, other_year):
                    diff_day += get_days_in_year(year)
            my_time = self.get_hour_minute_second()
            other_time = other.get_hour_minute_second()
            diff_hour = my_time[0] - other_time[0]
            diff_minute = my_time[1] - other_time[1]
            diff_second = my_time[2] - other_time[2]
            return TimeInterval(years=diff_year, days=diff_day,
                                hours=diff_hour, minutes=diff_minute,
                                seconds=diff_second)
        if not isinstance(other, TimeInterval):
            raise TypeError(
                      "Invalid subtraction type " +
                      "'%s' - should be TimeInterval." %
                      type(other).__name__)
        duration = other
        return self.__add__(duration * -1)

    def _add_months(self, num_months):
        if num_months == 0:
            return
        was_ordinal_date = False
        was_week_date = False
        if not self.get_is_calendar_date():
            if self.get_is_ordinal_date():
                was_ordinal_date = True
            if self.get_is_week_date():
                was_week_date = True
            self.to_calendar_date()
        for i in range(abs(num_months)):
            if num_months > 0:
                self.month_of_year += 1
                if self.month_of_year > 12:
                    self.month_of_year -= 12
                    self.year += 1
            if num_months < 0:
                self.month_of_year -= 1
                if self.month_of_year < 1:
                    self.month_of_year += 12
                    self.year -= 1
            month_index = (self.month_of_year - 1) % 12
            if get_is_leap_year(self.year):
                max_day_in_new_month = DAYS_OF_MONTHS_LEAP[month_index]
            else:
                max_day_in_new_month = DAYS_OF_MONTHS[month_index]
            if self.day_of_month > max_day_in_new_month:
                # For example, when 31 March + 1 month = 30 April.
                self.day_of_month = max_day_in_new_month
        self._tick_over()
        if was_ordinal_date:
            self.to_ordinal_date()
        if was_week_date:
            self.to_week_date()

    def _tick_over(self):
        """Correct all the units going from smallest to largest."""
        if self.second_of_minute is not None:
            num_minutes, seconds = divmod(self.second_of_minute, 60)
            self.minute_of_hour += num_minutes
            self.second_of_minute = seconds
        if self.minute_of_hour is not None:
            num_hours, minutes = divmod(self.minute_of_hour, 60)
            self.hour_of_day += num_hours
            self.minute_of_hour = minutes
        if self.hour_of_day is not None:
            num_days, hours = divmod(self.hour_of_day, 24)
            if self.day_of_week is not None:
                self.day_of_week += num_days
            elif self.day_of_month is not None:
                self.day_of_month += num_days
            elif self.day_of_year is not None:
                self.day_of_year += num_days
            self.hour_of_day = hours
        if self.day_of_week is not None:
            num_weeks, days = divmod(self.day_of_week - 1, 7)
            self.week_of_year += num_weeks
            self.day_of_week = days + 1
        if self.day_of_month is not None:
            self._tick_over_day_of_month()
        if self.day_of_year is not None:
            while self.day_of_year < 1:
                days_in_last_year = get_days_in_year(self.year - 1)
                self.day_of_year += days_in_last_year
                self.year -= 1
            while self.day_of_year > get_days_in_year(self.year):
                days_in_next_year = get_days_in_year(self.year + 1)
                self.day_of_year -= days_in_next_year
                self.year += 1
        if self.week_of_year is not None:
            while self.week_of_year < 1:
                weeks_in_last_year = get_weeks_in_year(self.year - 1)
                self.week_of_year += weeks_in_last_year
                self.year -= 1
            while self.week_of_year > get_weeks_in_year(self.year):
                weeks_in_this_year = get_weeks_in_year(self.year)
                self.week_of_year -= weeks_in_this_year
                self.year += 1
        if self.month_of_year is not None:
            while self.month_of_year < 1:
                self.month_of_year += 12
                self.year -= 1
            while self.month_of_year > 12:
                self.month_of_year -= 12
                self.year += 1

    def _tick_over_day_of_month(self):
        if self.day_of_month < 1:
            num_days = 2
            for month, day in iter_months_days(
                                    self.year,
                                    month_of_year=self.month_of_year,
                                    day_of_month=1, in_reverse=True):
                num_days -= 1
                if num_days == self.day_of_month:
                    self.month_of_year = month
                    self.day_of_month = day
                    break
            else:
                start_year = self.year
                while num_days != self.day_of_month:
                    start_year -= 1
                    for month, day in iter_months_days(
                                            start_year, in_reverse=True):
                        num_days -= 1
                        if num_days == self.day_of_month:
                            break
                self.year = start_year
                self.month_of_year = month
                self.day_of_month = day
        else:
            month_index = (self.month_of_year - 1) % 12
            if get_is_leap_year(self.year):
                max_day_in_month = DAYS_OF_MONTHS_LEAP[month_index]
            else:
                max_day_in_month = DAYS_OF_MONTHS[month_index]
            if self.day_of_month > max_day_in_month:
                num_days = 0
                for month, day in iter_months_days(
                                        self.year,
                                        month_of_year=self.month_of_year,
                                        day_of_month=1):
                    num_days += 1
                    if num_days == self.day_of_month:
                        self.month_of_year = month
                        self.day_of_month = day
                        break
                else:
                    start_year = self.year
                    while num_days != self.day_of_month:
                        start_year += 1
                        for month, day in iter_months_days(start_year):
                            num_days += 1
                            if num_days == self.day_of_month:
                                self.year = start_year
                                self.month_of_year = month
                                self.day_of_month = day
                                return

    def __str__(self, override_custom=False):
        if self.format_function is not None and not override_custom:
            return self.format_function(self)
        year_digits = 4 + self.expanded_year_digits
        year_string = "%0" + str(year_digits) + "d"
        if self.expanded_year_digits:
            if self.year < 0:
                year_string = "-" + year_string % abs(self.year)
            else:
                year_string = "+" + year_string % abs(self.year)
        elif self.year is not None and self.year < 0:
            raise OverflowError(
                      "Year %s can only be represented in expanded format" %
                      self.year)
        elif self.year is not None:
            year_string = year_string % self.year
        if self.truncated:
            year_string = "-"
            if self.truncated_property == "year_of_decade":
                year_string = "-" + str(self.year % 10)
            elif self.truncated_property == "year_of_century":
                year_string = "-" + str(self.year % 100)
        date_string = year_string
        if self.truncated:
            if self.month_of_year is not None:
                date_string = year_string + "-%02d" % self.month_of_year
                if self.day_of_month is not None:
                    date_string += "-%02d" % self.day_of_month
            elif self.day_of_month is not None:
                date_string = year_string + "-%02d" % self.day_of_month
            if self.day_of_year is not None:
                day_string = "%03d" % self.day_of_year
                if year_string == "-":
                    date_string = year_string + day_string
                else:
                    date_string = year_string + "-" + day_string
            if self.week_of_year is not None:
                date_string = year_string + "-W%02d" % self.week_of_year
                if self.day_of_week is not None:
                    date_string += "-%01d" % self.day_of_week
            elif self.day_of_week is not None:
                date_string = year_string + "-W-%01d" % self.day_of_week
        else:
            if self.get_is_calendar_date():
                date_string = year_string + "-%02d-%02d" % (self.month_of_year,
                                                            self.day_of_month)
            if self.get_is_ordinal_date():
                date_string = year_string + "-%03d" % self.day_of_year
            if self.get_is_week_date():
                date_string = year_string + "-W%02d-%01d" % (self.week_of_year,
                                                             self.day_of_week)
        time_string = ""
        if self.hour_of_day is not None:
            time_string = "T%02d" % int(self.hour_of_day)
            if int(self.hour_of_day) != self.hour_of_day:
                remainder = self.hour_of_day - int(self.hour_of_day)
                time_string += _format_remainder(remainder)
            else:
                if self.truncated and self.minute_of_hour is None:
                    time_string += ":00:00"
                else:
                    time_string += ":%02d" % int(self.minute_of_hour)
                    if int(self.minute_of_hour) != self.minute_of_hour:
                        remainder = self.minute_of_hour - int(self.minute_of_hour)
                        time_string += _format_remainder(remainder)
                    else:
                        if self.truncated and self.second_of_minute is None:
                            time_string += ":00"
                        else:
                            seconds_int = int(self.second_of_minute)
                            time_string += ":%02d" % seconds_int
                            if seconds_int != self.second_of_minute:
                                remainder = self.second_of_minute - seconds_int
                                time_string += _format_remainder(remainder)
        if time_string:
            time_string += str(self.time_zone)
        return date_string + time_string

    __repr__ = __str__


def cache_results(func):
    """Decorator to store results for given inputs.

    func is the decorated function.

    A maximum of 100000 arg-value pairs are stored.

    """
    cache = {}
    def wrap_func(*args, **kwargs):
        key = (str(args), str(kwargs))
        if key in cache:
            return cache[key]
        else:
            results = func(*args, **kwargs)
            if len(cache) < 100000:
                cache[key] = results
            return results
    return wrap_func


def _format_remainder(float_time_number):
    """Format a floating point remainder of a time unit."""
    string = "," + ("%f" % float_time_number)[2:].rstrip("0")
    if string == ",":
        return ""
    return string


@cache_results
def get_is_leap_year(year):
    """Return if year is a leap year in the proleptic Gregorian calendar."""
    if year % 4 == 0:
        # A multiple of 4.
        if year % 100 == 0 and year % 400 != 0:
            # A centennial leap year must be a multiple of 400.
            return False
        return True
    return False


@cache_results
def get_days_in_year(year):
    """Return 366 if year is a leap year, otherwise 365."""
    if get_is_leap_year(year):
        return 366
    return 365


@cache_results
def get_weeks_in_year(year):
    """Return the number of calendar weeks in this week date year."""
    cal_year, cal_ord_days = get_ordinal_date_week_date_start(year)
    cal_year_next, cal_ord_days_next = get_ordinal_date_week_date_start(
                                                             year + 1)
    diff_days = cal_ord_days_next - cal_ord_days
    while cal_year_next != cal_year:
        diff_days += get_days_in_year(cal_year)
        cal_year += 1
    return diff_days / 7


def get_calendar_date_from_ordinal_date(year, day_of_year):
    """Translate an ordinal date into a calendar date.

    Returns the calendar year, calendar month, calendar day-of-month.

    Arguments:
    year is an integer that denotes the ordinal date year
    day_of_year is an integer that denotes the ordinal day in the year.

    """
    iter_num_days = 0
    for iter_month, iter_day in iter_months_days(year):
        iter_num_days += 1
        if iter_num_days == day_of_year:
            return year, iter_month, iter_day
    raise ValueError("Bad ordinal date: %s-%03d" % (year, day_of_year))


def get_calendar_date_from_week_date(year, week_of_year, day_of_week):
    """Translate a week date into a calendar date.

    Returns the calendar year, calendar month, calendar day-of-month.

    Arguments:
    year is an integer that denotes the week date year (may differ
    from calendar year)
    week_of_year is an integer that denotes the week number in the year
    day_of_week is an integer that denotes the day of the week (1-7).

    """
    num_days_week_year = (week_of_year - 1) * 7 + day_of_week - 1
    start_year, start_month, start_day = get_calendar_date_week_date_start(year)
    if num_days_week_year == 0:
        return start_year, start_month, start_day
    total_iter_days = 0
    # Loop over the months and days left in the start year.
    for iter_month, iter_day in iter_months_days(
                                        start_year,
                                        month_of_year=start_month,
                                        day_of_month=start_day + 1):
        total_iter_days += 1
        if num_days_week_year == total_iter_days:
            return start_year, iter_month, iter_day
    if start_year < year:
        # We've only looped over the last year - now the current one.
        for iter_month, iter_day in iter_months_days(year):
            total_iter_days += 1
            if num_days_week_year == total_iter_days:
                return year, iter_month, iter_day                
    for iter_month, iter_day in iter_months_days(year + 1):
        # Loop over the following year.
        total_iter_days += 1
        if num_days_week_year == total_iter_days:
            return year + 1, iter_month, iter_day
    raise ValueError("Bad week date: %s-W%02d-%s" % (year,
                                                     week_of_year,
                                                     day_of_week))


def get_ordinal_date_from_calendar_date(year, month_of_year, day_of_month):
    """Translate a calendar date into an ordinal date.

    Returns the ordinal year, calendar month, calendar day-of-month.

    Arguments:
    year is an integer that denotes the year
    month_of_year is an integer that denotes the month number in the
    year.
    day_of_month is an integer that denotes the day number in the
    month_of_year.

    """
    iter_num_days = 0
    for iter_month, iter_day in iter_months_days(year):
        iter_num_days += 1
        if iter_month == month_of_year and iter_day == day_of_month:
            return year, iter_num_days
    raise ValueError("Bad calendar date: %s-%02d-%02d" % (year,
                                                          month_of_year,
                                                          day_of_month))


def get_ordinal_date_from_week_date(year, week_of_year, day_of_week):
    """Translate a week date into an ordinal date.

    Returns the ordinal year, ordinal day-of-year.

    Arguments:
    year is an integer that denotes the week date year (which may
    differ from the ordinal or calendar year)
    week_of_year is an integer that denotes the week number in the
    year.
    day_of_week is an integer that denotes the day number in the
    week_of_year.

    """
    cal_year, cal_month, cal_day_of_month = get_calendar_date_from_week_date(
                                            year, week_of_year, day_of_week)
    return get_ordinal_date_from_calendar_date(
                                 cal_year, cal_month, cal_day_of_month)


def get_week_date_from_calendar_date(year, month_of_year, day_of_month):
    """Translate a calendar date into an week date.

    Returns the week date year, week-of-year, day-of-week.

    Arguments:
    year is an integer that denotes the calendar year, which may
    differ from the week date year.
    month_of_year is an integer that denotes the month number in the
    above year.
    day_of_month is an integer that denotes the day number in the
    above month_of_year.

    """
    prev_start = get_calendar_date_week_date_start(year - 1)
    this_start = get_calendar_date_week_date_start(year)
    next_start = get_calendar_date_week_date_start(year + 1)

    cal_date = (year, month_of_year, day_of_month)
    
    if prev_start <= cal_date < this_start:
        # This calendar date is in the previous week date year.
        start_year, start_month, start_day = prev_start
        week_date_start_year = year - 1
    elif this_start <= cal_date < next_start:
        # This calendar date is in the same week date year.
        start_year, start_month, start_day = this_start
        week_date_start_year = year
    else:
        # This calendar date is in the next week date year.
        start_year, start_month, start_day = next_start
        week_date_start_year = year + 1

    total_iter_days = -1
    # A week date year can theoretically span 3 calendar years...
    for iter_month, iter_day in iter_months_days(start_year,
                                                 month_of_year=start_month,
                                                 day_of_month=start_day):
        total_iter_days += 1
        if (start_year == year and
            iter_month == month_of_year and
            iter_day == day_of_month):
            week_of_year = (total_iter_days / 7) + 1
            day_of_week = (total_iter_days % 7) + 1
            return week_date_start_year, week_of_year, day_of_week

    for iter_start_year in [start_year + 1, start_year + 2]:
        # Look at following year when the calendar date is e.g. very early Jan.
        for iter_month, iter_day in iter_months_days(iter_start_year):
            total_iter_days += 1
            if (iter_start_year == year and
                iter_month == month_of_year and
                iter_day == day_of_month):
                week_of_year = (total_iter_days / 7) + 1
                day_of_week = (total_iter_days % 7) + 1
                return week_date_start_year, week_of_year, day_of_week
    raise ValueError("Bad calendar date: %s-%02d-%02d" % (year,
                                                          month_of_year,
                                                          day_of_month))


def get_week_date_from_ordinal_date(year, day_of_year):
    """Translate an ordinal date into a week date.

    Returns the week date year, week-of-year, day-of-week.

    Arguments:
    year is an integer that denotes the ordinal date year, which
    may differ from the week date year.
    day_of_year is an integer that denotes the ordinal day in the year.

    """
    year, month, day = get_calendar_date_from_ordinal_date(year, day_of_year)
    return get_week_date_from_calendar_date(year, month, day)


@cache_results
def get_calendar_date_week_date_start(year):
    """Return the calendar date of the start of (week date) year."""
    ref_year, ref_month, ref_day = WEEK_DAY_START_REFERENCE["calendar"]
    ref_year, ref_ordinal_day = WEEK_DAY_START_REFERENCE["ordinal"]
    if year == ref_year:
        return ref_year, ref_month, ref_day
    # Calculate the weekday for 1 January in this calendar year.
    if year > ref_year:
        years = range(ref_year, year)
        days_diff = 1 - ref_ordinal_day
    else:
        years = range(ref_year - 1, year - 1, -1)
        days_diff = ref_ordinal_day - 2
    for intervening_year in years:
        days_diff += get_days_in_year(intervening_year)
    weekdays_diff = (days_diff) % 7
    if year > ref_year:
        day_of_week_start_year = weekdays_diff + 1
    else:
        day_of_week_start_year = 7 - weekdays_diff # Jan 1 as day of week.       
    if day_of_week_start_year == 1:
        return year, 1, 1
    if day_of_week_start_year > 4:
        # This week belongs to the previous year; get the next Monday.
        day = 1 + (8 - day_of_week_start_year)
        return year, 1, day
    # The week starts in the previous year - get the previous Monday.
    for month, day in iter_months_days(year - 1, in_reverse=True):
        day_of_week_start_year -= 1
        if day_of_week_start_year == 1:
            return year - 1, month, day


@cache_results
def get_days_since_1_ad(year):
    """Return the number of days since Jan 1, 1 A.D. to the year end."""
    if year == 1:
        return get_days_in_year(year)
    elif year < 1:
        return 0
    start_year = 0
    days = 0
    while start_year < year:
        start_year += 1
        days += get_days_in_year(start_year)
    return days


@cache_results
def get_ordinal_date_week_date_start(year):
    """Return the week date start for year in year, day-of-year."""
    cal_year, cal_month, cal_day = get_calendar_date_week_date_start(year)
    total_days = 0
    for iter_month, iter_day in iter_months_days(cal_year):
        total_days += 1
        if iter_month == cal_month and iter_day == cal_day:
            return cal_year, total_days


def iter_months_days(year, month_of_year=None, day_of_month=None,
                     in_reverse=False):
    """Iterate over each day in each month of year.

    year is an integer specifying the year to use.
    month_of_year is an optional integer, specifying a start month.
    day_of_month is an optional integer, specifying a start day.
    in_reverse is an optional boolean that reverses the iteration if
    True (default False).

    """
    source = DAYS_OF_MONTHS
    if get_is_leap_year(year):
        source = DAYS_OF_MONTHS_LEAP
    if day_of_month is not None and month_of_year is None:
        raise ValueError("Need to specify start month as well as day.")
    if in_reverse:
        if month_of_year is None:
            for i, days in enumerate(reversed(source)):
                day_range = range(days, 0, -1)
                j = len(source) - i
                for day in day_range:
                    yield j, day
        else:
            for i, days in enumerate(reversed(source)):
                j = len(source) - i
                if j > month_of_year:
                    continue
                elif j == month_of_year and day_of_month is not None:
                    day_range = range(day_of_month, 0, -1)
                else:
                    day_range = range(days, 0, -1)
                for day in day_range:
                    yield j, day
    else:
        if month_of_year is None:
            for i, days in enumerate(source):
                day_range = range(1, days + 1)
                for day in day_range:
                    yield i + 1, day
        else:
            for i, days in enumerate(source):
                if i + 1 < month_of_year:
                    continue
                elif i + 1 == month_of_year and day_of_month is not None:
                    day_range = range(day_of_month, days + 1)
                else:
                    day_range = range(1, days + 1)
                for day in day_range:
                    yield i + 1, day


class TestSuite(unittest.TestCase):

    """Test the functionality of parsers and data model manipulation."""

    def assertEqual(self, test, control, source=None):
        """Override the assertEqual method to provide more information."""
        if source is None:
            info = None
        else:
            info = ("Source %s produced\n%s, should be\n%s" %
                    (source, test, control))
        super(TestSuite, self).assertEqual(test, control, info)

    def test_timeinterval_parser(self):
        """Test the time interval parsing."""
        parser = TimeIntervalParser()
        for expression, ctrl_result in parser.get_tests():
            try:
                test_result = str(parser.parse(expression))
            except TimeSyntaxError:
                raise ValueError(
                            "TimeIntervalParser test failed to parse '%s'" %
                            expression)
            self.assertEqual(test_result, ctrl_result, expression)

    def test_timepoint(self):
        """Test the manipulation of dates and times (takes a while)."""
        import datetime
        import random
        my_date = datetime.datetime(1801, 1, 1)
        while my_date <= datetime.datetime(2401, 2, 1):
            ctrl_data = my_date.isocalendar()
            test_date = TimePoint(year=my_date.year, month_of_year=my_date.month,
                                  day_of_month=my_date.day)
            test_data = test_date.get_week_date()
            self.assertEqual(test_data, ctrl_data)
            ctrl_data = (my_date.year, my_date.month, my_date.day)
            test_data = test_date.to_week_date().get_calendar_date()
            self.assertEqual(test_data, ctrl_data)
            ctrl_data = my_date.toordinal()
            year, day_of_year = test_date.get_ordinal_date()
            test_data = day_of_year
            test_data += get_days_since_1_ad(year - 1)
            self.assertEqual(test_data, ctrl_data)
            for attribute, attr_max in [("weeks", 110),
                                        ("days", 770),
                                        ("hours", 770*24),
                                        ("minutes", 770 * 24 * 60),
                                        ("seconds", 770 * 24 * 60 * 60)]:
                delta_attr = random.randrange(0, attr_max)
                kwargs = {attribute: delta_attr}
                ctrl_data = my_date + datetime.timedelta(**kwargs)
                ctrl_data = (ctrl_data.year, ctrl_data.month, ctrl_data.day)
                test_data = (test_date + TimeInterval(**kwargs)).get_calendar_date()
                self.assertEqual(test_data, ctrl_data)
                ctrl_data = (my_date - datetime.timedelta(**kwargs))
                ctrl_data = (ctrl_data.year, ctrl_data.month, ctrl_data.day)
                test_data = (test_date - TimeInterval(**kwargs)).get_calendar_date()
                self.assertEqual(test_data, ctrl_data)
            ctrl_data = (my_date + datetime.timedelta(minutes=450) +
                         datetime.timedelta(hours=5) -
                         datetime.timedelta(seconds=500, weeks=5))
            ctrl_data = [(ctrl_data.year, ctrl_data.month, ctrl_data.day),
                         (ctrl_data.hour, ctrl_data.minute, ctrl_data.second)]
            test_data = (test_date + TimeInterval(minutes=450) +
                         TimeInterval(hours=5) - TimeInterval(weeks=5, seconds=500))
            test_data = [test_data.get_calendar_date(),
                         test_data.get_hour_minute_second()]
            self.assertEqual(test_data, ctrl_data)
            timedelta = datetime.timedelta(days=1)
            my_date += timedelta

    def test_timepoint_parser(self):
        """Test the parsing of date/time expressions."""
        parser = TimePointParser(allow_truncated=True)
        for expression, timepoint_kwargs in parser.get_tests():
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_data = str(parser.parse(expression))
            except TimeSyntaxError:
                raise ValueError("Parsing failed for %s" % expression)
            ctrl_data = str(TimePoint(**timepoint_kwargs))
            self.assertEqual(test_data, ctrl_data, expression)

    def test_timerecurrence(self):
        """Test the recurring date/time series data model."""
        parser = TimeRecurrenceParser()
        for expression, ctrl_results in TimeRecurrence.TEST_EXPRESSIONS:
            try:
                test_recurrence = parser.parse(expression)
            except TimeSyntaxError:
                raise ValueError(
                            "TimeRecurrenceParser test failed to parse '%s'" %
                            expression)
            test_results = []
            for i, time_point in enumerate(test_recurrence):
                if i > 2:
                    break
                test_results.append(str(time_point))
            self.assertEqual(test_results, ctrl_results, expression)

    def test_timerecurrence_parser(self):
        """Test the recurring date/time series parsing."""
        parser = TimeRecurrenceParser()
        for expression, test_info in parser.get_tests():
            try:
                test_data = str(parser.parse(expression))
            except TimeSyntaxError:
                raise ValueError("Parsing failed for %s" % expression)
            ctrl_data = str(TimeRecurrence(**test_info))
            self.assertEqual(test_data, ctrl_data, expression)


def parse_timepoint_expression(timepoint_expression, **kwargs):
    parser = TimePointParser(**kwargs)
    return parser.parse(timepoint_expression)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSuite)
    unittest.TextTestRunner(verbosity=2).run(suite)
