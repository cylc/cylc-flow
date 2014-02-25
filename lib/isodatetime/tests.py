# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# (C) British Crown Copyright 2013-2014 Met Office.
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

"""This tests the ISO 8601 parsing and data model functionality."""

import copy
import unittest

from . import data
from . import parsers
from . import parser_spec


def get_timeintervalparser_tests():
    """Yield tests for the time interval parser."""
    test_expressions = {
        "P3Y": str(data.TimeInterval(years=3)),
        "P90Y": str(data.TimeInterval(years=90)),
        "P1Y2M": str(data.TimeInterval(years=1, months=2)),
        "P20Y2M": str(data.TimeInterval(years=20, months=2)),
        "P2M": str(data.TimeInterval(months=2)),
        "P52M": str(data.TimeInterval(months=52)),
        "P20Y10M2D": str(data.TimeInterval(years=20, months=10, days=2)),
        "P1Y3D": str(data.TimeInterval(years=1, days=3)),
        "P4M1D": str(data.TimeInterval(months=4, days=1)),
        "P3Y404D": str(data.TimeInterval(years=3, days=404)),
        "P30Y2D": str(data.TimeInterval(years=30, days=2)),
        "PT6H": str(data.TimeInterval(hours=6)),
        "PT1034H": str(data.TimeInterval(hours=1034)),
        "P3YT4H2M": str(data.TimeInterval(years=3, hours=4, minutes=2)),
        "P30Y2DT10S": str(data.TimeInterval(years=30, days=2, seconds=10)),
        "PT2S": str(data.TimeInterval(seconds=2)),
        "PT2.5S": str(data.TimeInterval(seconds=2.5)),
        "PT2,5S": str(data.TimeInterval(seconds=2.5)),
        "PT5.5023H": str(data.TimeInterval(hours=5.5023)),
        "PT5,5023H": str(data.TimeInterval(hours=5.5023)),
        "P5W": str(data.TimeInterval(weeks=5)),
        "P100W": str(data.TimeInterval(weeks=100))
    }
    for expression, ctrl_result in test_expressions.items():
        yield expression, ctrl_result


def get_timepointdumper_tests():
    return


def get_timepointparser_tests(allow_only_basic=False,
                              allow_truncated=False):
    """Yield tests for the time point parser."""
    # Note: test dates assume 2 expanded year digits.
    test_date_map = {
        "basic": {
            "complete": {
                "00440104": {"year": 44, "month_of_year": 1,
                             "day_of_month": 4},
                "+5002000830": {"year": 500200, "month_of_year": 8,
                                "day_of_month": 30,
                                "expanded_year_digits": 2},
                "-0000561113": {"year": -56, "month_of_year": 11,
                                "day_of_month": 13,
                                "expanded_year_digits": 2},
                "-1000240210": {"year": -100024, "month_of_year": 2,
                                "day_of_month": 10,
                                "expanded_year_digits": 2},
                "1967056": {"year": 1967, "day_of_year": 56},
                "+123456078": {"year": 123456, "day_of_year": 78,
                               "expanded_year_digits": 2},
                "-004560134": {"year": -4560, "day_of_year": 134,
                               "expanded_year_digits": 2},
                "1001W011": {"year": 1001, "week_of_year": 1,
                             "day_of_week": 1},
                "+000001W457": {"year": 1, "week_of_year": 45,
                                "day_of_week": 7,
                                "expanded_year_digits": 2},
                "-010001W053": {"year": -10001, "week_of_year": 5,
                                "day_of_week": 3, "expanded_year_digits": 2}
            },
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
                               "expanded_year_digits": 2}
            },
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
                "-W031": {"week_of_year": 3, "day_of_week": 1,
                          "truncated": True},
                "-W32": {"week_of_year": 32, "truncated": True},
                "-W-1": {"day_of_week": 1, "truncated": True}
            }
        },
        "extended": {
            "complete": {
                "0044-01-04": {"year": 44, "month_of_year": 1,
                               "day_of_month": 4},
                "+500200-08-30": {"year": 500200, "month_of_year": 8,
                                  "day_of_month": 30,
                                  "expanded_year_digits": 2},
                "-000056-11-13": {"year": -56, "month_of_year": 11,
                                  "day_of_month": 13,
                                  "expanded_year_digits": 2},
                "-100024-02-10": {"year": -100024, "month_of_year": 2,
                                  "day_of_month": 10,
                                  "expanded_year_digits": 2},
                "1967-056": {"year": 1967, "day_of_year": 56},
                "+123456-078": {"year": 123456, "day_of_year": 78,
                                "expanded_year_digits": 2},
                "-004560-134": {"year": -4560, "day_of_year": 134,
                                "expanded_year_digits": 2},
                "1001-W01-1": {"year": 1001, "week_of_year": 1,
                               "day_of_week": 1},
                "+000001-W45-7": {"year": 1, "week_of_year": 45,
                                  "day_of_week": 7,
                                  "expanded_year_digits": 2},
                "-010001-W05-3": {"year": -10001, "week_of_year": 5,
                                  "day_of_week": 3,
                                  "expanded_year_digits": 2}
            },
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
                                "expanded_year_digits": 2}
            },
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
                "-W03-1": {"week_of_year": 3, "day_of_week": 1,
                           "truncated": True},
                "-W32": {"week_of_year": 32, "truncated": True},
                "-W-1": {"day_of_week": 1, "truncated": True}
            }
        }
    }
    test_time_map = {
        "basic": {
            "complete": {
                "050102": {"hour_of_day": 5, "minute_of_hour": 1,
                           "second_of_minute": 2},
                "235902,345": {"hour_of_day": 23, "minute_of_hour": 59,
                               "second_of_minute": 2,
                               "second_of_minute_decimal": 0.345},
                "235902.345": {"hour_of_day": 23, "minute_of_hour": 59,
                               "second_of_minute": 2,
                               "second_of_minute_decimal": 0.345},
                "1201,4": {"hour_of_day": 12, "minute_of_hour": 1,
                           "minute_of_hour_decimal": 0.4},
                "1201.4": {"hour_of_day": 12, "minute_of_hour": 1,
                           "minute_of_hour_decimal": 0.4},
                "00,4356": {"hour_of_day": 0,
                            "hour_of_day_decimal": 0.4356},
                "00.4356": {"hour_of_day": 0,
                            "hour_of_day_decimal": 0.4356}
            },
            "reduced": {
                "0203": {"hour_of_day": 2, "minute_of_hour": 3},
                "17": {"hour_of_day": 17}
            },
            "truncated": {
                "-5612": {"minute_of_hour": 56, "second_of_minute": 12,
                          "truncated": True},
                "-12": {"minute_of_hour": 12, "truncated": True},
                "--45": {"second_of_minute": 45, "truncated": True},
                "-1234,45": {"minute_of_hour": 12, "second_of_minute": 34,
                             "second_of_minute_decimal": 0.45,
                             "truncated": True},
                "-1234.45": {"minute_of_hour": 12, "second_of_minute": 34,
                             "second_of_minute_decimal": 0.45,
                             "truncated": True},
                "-34,2": {"minute_of_hour": 34, "minute_of_hour_decimal": 0.2,
                          "truncated": True},
                "-34.2": {"minute_of_hour": 34, "minute_of_hour_decimal": 0.2,
                          "truncated": True},
                "--59,99": {"second_of_minute": 59,
                            "second_of_minute_decimal": 0.99,
                            "truncated": True},
                "--59.99": {"second_of_minute": 59,
                            "second_of_minute_decimal": 0.99,
                            "truncated": True}
            }
        },
        "extended": {
            "complete": {
                "05:01:02": {"hour_of_day": 5, "minute_of_hour": 1,
                             "second_of_minute": 2},
                "23:59:02,345": {"hour_of_day": 23, "minute_of_hour": 59,
                                 "second_of_minute": 2,
                                 "second_of_minute_decimal": 0.345},
                "23:59:02.345": {"hour_of_day": 23, "minute_of_hour": 59,
                                 "second_of_minute": 2,
                                 "second_of_minute_decimal": 0.345},
                "12:01,4": {"hour_of_day": 12, "minute_of_hour": 1,
                            "minute_of_hour_decimal": 0.4},
                "12:01.4": {"hour_of_day": 12, "minute_of_hour": 1,
                            "minute_of_hour_decimal": 0.4},
                "00,4356": {"hour_of_day": 0, "hour_of_day_decimal": 0.4356},
                "00.4356": {"hour_of_day": 0, "hour_of_day_decimal": 0.4356}
            },
            "reduced": {
                "02:03": {"hour_of_day": 2, "minute_of_hour": 3},
                "17": {"hour_of_day": 17}
            },
            "truncated": {
                "-56:12": {"minute_of_hour": 56, "second_of_minute": 12,
                           "truncated": True},
                "-12": {"minute_of_hour": 12, "truncated": True},
                "--45": {"second_of_minute": 45, "truncated": True},
                "-12:34,45": {"minute_of_hour": 12, "second_of_minute": 34,
                              "second_of_minute_decimal": 0.45,
                              "truncated": True},
                "-12:34.45": {"minute_of_hour": 12, "second_of_minute": 34,
                              "second_of_minute_decimal": 0.45,
                              "truncated": True},
                "-34,2": {"minute_of_hour": 34, "minute_of_hour_decimal": 0.2,
                          "truncated": True},
                "-34.2": {"minute_of_hour": 34, "minute_of_hour_decimal": 0.2,
                          "truncated": True},
                "--59,99": {"second_of_minute": 59,
                            "second_of_minute_decimal": 0.99,
                            "truncated": True},
                "--59.99": {"second_of_minute": 59,
                            "second_of_minute_decimal": 0.99,
                            "truncated": True}
            }
        }
    }
    test_timezone_map = {
        "basic": {
            "Z": {"time_zone_hour": 0, "time_zone_minute": 0},
            "+01": {"time_zone_hour": 1},
            "-05": {"time_zone_hour": -5},
            "+2301": {"time_zone_hour": 23, "time_zone_minute": 1},
            "-1230": {"time_zone_hour": -12, "time_zone_minute": -30}
        },
        "extended": {
            "Z": {"time_zone_hour": 0, "time_zone_minute": 0},
            "+01": {"time_zone_hour": 1},
            "-05": {"time_zone_hour": -5},
            "+23:01": {"time_zone_hour": 23, "time_zone_minute": 1},
            "-12:30": {"time_zone_hour": -12, "time_zone_minute": -30}
        }
    }
    format_ok_keys = ["basic", "extended"]
    if allow_only_basic:
        format_ok_keys = ["basic"]
    date_combo_ok_keys = ["complete"]
    if allow_truncated:
        date_combo_ok_keys = ["complete", "truncated"]
    time_combo_ok_keys = ["complete", "reduced"]
    time_designator = parser_spec.TIME_DESIGNATOR
    for format_type in format_ok_keys:
        date_format_tests = test_date_map[format_type]
        time_format_tests = test_time_map[format_type]
        timezone_format_tests = test_timezone_map[format_type]
        for date_key in date_format_tests:
            if not allow_truncated and date_key == "truncated":
                continue
            for date_expr, info in date_format_tests[date_key].items():
                yield date_expr, info
        for date_key in date_combo_ok_keys:
            date_tests = date_format_tests[date_key]
            # Add a blank date for time-only testing.
            for date_expr, info in date_tests.items():
                for time_key in time_combo_ok_keys:
                    time_items = time_format_tests[time_key].items()
                    for time_expr, time_info in time_items:
                        combo_expr = (
                            date_expr +
                            time_designator +
                            time_expr
                        )
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
        if not allow_truncated:
            continue
        for time_key in time_format_tests:
            time_tests = time_format_tests[time_key]
            for time_expr, time_info in time_tests.items():
                combo_expr = (
                    time_designator +
                    time_expr
                )
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


def get_timerecurrence_tests():
    """Return test expressions for data.TimeRecurrence."""
    return [
        ("R3/1001-W01-1T00:00:00Z/1002-W52-6T00:00:00-05:30",
         ["1001-W01-1T00:00:00Z", "1001-W53-3T14:45:00Z",
          "1002-W52-6T05:30:00Z"]),
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
          "-100024-02-11T04:00:00-12:30"])
    ]


def get_timerecurrenceparser_tests():
    """Yield tests for the time recurrence parser."""
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
        point_parser = parsers.TimePointParser()
        interval_parser = parsers.TimeIntervalParser()
        for point_expr in test_points:
            interval_tests = get_timeintervalparser_tests()
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


class TestSuite(unittest.TestCase):

    """Test the functionality of parsers and data model manipulation."""

    def assertEqual(self, test, control, source=None):
        """Override the assertEqual method to provide more information."""
        if source is None:
            info = None
        else:
            info = ("Source %s produced:\n'%s'\nshould be:\n'%s'" %
                    (source, test, control))
        super(TestSuite, self).assertEqual(test, control, info)

    def test_timeinterval_parser(self):
        """Test the time interval parsing."""
        parser = parsers.TimeIntervalParser()
        for expression, ctrl_result in get_timeintervalparser_tests():
            try:
                test_result = str(parser.parse(expression))
            except TimeSyntaxError:
                raise ValueError(
                    "TimeIntervalParser test failed to parse '%s'" %
                    expression
                )
            self.assertEqual(test_result, ctrl_result, expression)

    def test_timepoint(self):
        """Test the manipulation of dates and times (takes a while)."""
        import datetime
        import random
        my_date = datetime.datetime(1801, 1, 1)
        while my_date <= datetime.datetime(2401, 2, 1):
            ctrl_data = my_date.isocalendar()
            test_date = data.TimePoint(
                year=my_date.year,
                month_of_year=my_date.month,
                day_of_month=my_date.day)
            test_data = test_date.get_week_date()
            self.assertEqual(test_data, ctrl_data)
            ctrl_data = (my_date.year, my_date.month, my_date.day)
            test_data = test_date.to_week_date().get_calendar_date()
            self.assertEqual(test_data, ctrl_data)
            ctrl_data = my_date.toordinal()
            year, day_of_year = test_date.get_ordinal_date()
            test_data = day_of_year
            test_data += data.get_days_since_1_ad(year - 1)
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
                test_data = (
                    test_date + data.TimeInterval(
                        **kwargs)).get_calendar_date()
                self.assertEqual(test_data, ctrl_data)
                ctrl_data = (my_date - datetime.timedelta(**kwargs))
                ctrl_data = (ctrl_data.year, ctrl_data.month, ctrl_data.day)
                test_data = (
                    test_date - data.TimeInterval(
                        **kwargs)).get_calendar_date()
                self.assertEqual(test_data, ctrl_data)
            ctrl_data = (my_date + datetime.timedelta(minutes=450) +
                         datetime.timedelta(hours=5) -
                         datetime.timedelta(seconds=500, weeks=5))
            ctrl_data = [(ctrl_data.year, ctrl_data.month, ctrl_data.day),
                         (ctrl_data.hour, ctrl_data.minute, ctrl_data.second)]
            test_data = (
                test_date + data.TimeInterval(minutes=450) +
                data.TimeInterval(hours=5) -
                data.TimeInterval(weeks=5, seconds=500)
            )
            test_data = [test_data.get_calendar_date(),
                         test_data.get_hour_minute_second()]
            self.assertEqual(test_data, ctrl_data)
            timedelta = datetime.timedelta(days=1)
            my_date += timedelta

    def test_timepoint_dumper(self):
        """Test the dumping of TimePoint instances."""
        parser = parsers.TimePointParser(allow_truncated=True)
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True):
            ctrl_timepoint = data.TimePoint(**timepoint_kwargs)
            try:
                test_timepoint = parser.parse(str(ctrl_timepoint))
            except parsers.TimeSyntaxError as syn_exc:
                raise ValueError(
                    "Parsing failed for the dump of {0}: {1}".format(
                        expression, syn_exc))
            self.assertEqual(test_timepoint,
                             ctrl_timepoint, expression)

    def test_timepoint_parser(self):
        """Test the parsing of date/time expressions."""
        parser = parsers.TimePointParser(allow_truncated=True)
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True):
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_data = str(parser.parse(expression))
            except parsers.TimeSyntaxError as syn_exc:
                raise ValueError("Parsing failed for {0}: {1}".format(
                   expression, syn_exc))
            ctrl_data = str(data.TimePoint(**timepoint_kwargs))
            self.assertEqual(test_data, ctrl_data, expression)

    def test_timerecurrence(self):
        """Test the recurring date/time series data model."""
        parser = parsers.TimeRecurrenceParser()
        for expression, ctrl_results in get_timerecurrence_tests():
            try:
                test_recurrence = parser.parse(expression)
            except parsers.TimeSyntaxError:
                raise ValueError(
                    "TimeRecurrenceParser test failed to parse '%s'" %
                    expression
                )
            test_results = []
            for i, time_point in enumerate(test_recurrence):
                if i > 2:
                    break
                test_results.append(str(time_point))
            self.assertEqual(test_results, ctrl_results, expression)

    def test_timerecurrence_parser(self):
        """Test the recurring date/time series parsing."""
        parser = parsers.TimeRecurrenceParser()
        for expression, test_info in get_timerecurrenceparser_tests():
            try:
                test_data = str(parser.parse(expression))
            except parsers.TimeSyntaxError:
                raise ValueError("Parsing failed for %s" % expression)
            ctrl_data = str(data.TimeRecurrence(**test_info))
            self.assertEqual(test_data, ctrl_data, expression)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSuite)
    unittest.TextTestRunner(verbosity=2).run(suite)
