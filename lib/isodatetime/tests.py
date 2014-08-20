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
import multiprocessing
import unittest

from . import data
from . import dumpers
from . import parsers
from . import parser_spec


def get_timeduration_tests():
    """Yield tests for the duration class."""
    tests = {
        "get_days_and_seconds": [
            ([], {"hours": 25}, (1, 3600)),
            ([], {"seconds": 59}, (0, 59)),
            ([], {"minutes": 10}, (0, 600)),
            ([], {"days": 5, "minutes": 2}, (5, 120)),
            ([], {"hours": 2, "minutes": 5, "seconds": 11.5}, (0, 7511.5)),
            ([], {"hours": 23, "minutes": 1446}, (1, 83160))
        ],
        "get_seconds": [
            ([], {"hours": 25}, 90000),
            ([], {"seconds": 59}, 59),
            ([], {"minutes": 10}, 600),
            ([], {"days": 5, "minutes": 2}, 432120),
            ([], {"hours": 2, "minutes": 5, "seconds": 11.5}, 7511.5),
            ([], {"hours": 23, "minutes": 1446}, 169560)
        ]
    }
    for method, method_tests in tests.items():
        for method_args, test_props, ctrl_results in method_tests:
            yield test_props, method, method_args, ctrl_results


def get_timedurationparser_tests():
    """Yield tests for the duration parser."""
    test_expressions = {
        "P3Y": {"years": 3},
        "P90Y": {"years": 90},
        "P1Y2M": {"years": 1, "months": 2},
        "P20Y2M": {"years": 20, "months": 2},
        "P2M": {"months": 2},
        "P52M": {"months": 52},
        "P20Y10M2D": {"years": 20, "months": 10, "days": 2},
        "P1Y3D": {"years": 1, "days": 3},
        "P4M1D": {"months": 4, "days": 1},
        "P3Y404D": {"years": 3, "days": 404},
        "P30Y2D": {"years": 30, "days": 2},
        "PT6H": {"hours": 6},
        "PT1034H": {"hours": 1034},
        "P3YT4H2M": {"years": 3, "hours": 4, "minutes": 2},
        "P30Y2DT10S": {"years": 30, "days": 2, "seconds": 10},
        "PT2S": {"seconds": 2},
        "PT2.5S": {"seconds": 2.5},
        "PT2,5S": {"seconds": 2.5},
        "PT5.5023H": {"hours": 5.5023},
        "PT5,5023H": {"hours": 5.5023},
        "P5W": {"weeks": 5},
        "P100W": {"weeks": 100},
        "P0004-03-02T01": {"years": 4, "months": 3, "days": 2,
                           "hours": 1},
        "P0004-03-00": {"years": 4, "months": 3},
        "P0004-078": {"years": 4, "days": 78},
        "P0004-078T10,5": {"years": 4, "days": 78, "hours": 10.5},
        "P00000020T133702": {"days": 20, "hours": 13, "minutes": 37,
                             "seconds": 02},
        "-P3YT4H2M": {"years": -3, "hours": -4, "minutes": -2},
        "-PT5M": {"minutes": -5},
        "-P7Y": {"years": -7, "hours": 0}
    }
    for expression, ctrl_result in test_expressions.items():
        ctrl_data = str(data.Duration(**ctrl_result))
        yield expression, ctrl_data


def get_timedurationdumper_tests():
    """Yield tests for the duration dumper."""
    test_expressions = {
        "P3Y": {"years": 3},
        "P90Y": {"years": 90},
        "P1Y2M": {"years": 1, "months": 2},
        "P20Y2M": {"years": 20, "months": 2},
        "P2M": {"months": 2},
        "P52M": {"months": 52},
        "P20Y10M2D": {"years": 20, "months": 10, "days": 2},
        "P1Y3D": {"years": 1, "days": 3},
        "P4M1D": {"months": 4, "days": 1},
        "P3Y404D": {"years": 3, "days": 404},
        "P30Y2D": {"years": 30, "days": 2},
        "PT6H": {"hours": 6},
        "PT1034H": {"hours": 1034},
        "P3YT4H2M": {"years": 3, "hours": 4, "minutes": 2},
        "P30Y2DT10S": {"years": 30, "days": 2, "seconds": 10},
        "PT2S": {"seconds": 2},
        "PT2,5S": {"seconds": 2.5},
        "PT5,5023H": {"hours": 5.5023},
        "P5W": {"weeks": 5},
        "P100W": {"weeks": 100},
        "-P3YT4H2M": {"years": -3, "hours": -4, "minutes": -2},
        "-PT5M": {"minutes": -5},
        "-P7Y": {"years": -7, "hours": 0},
        "PT1H": {"seconds": 3600, "standardize": True},
        "P1DT5M": {"minutes": 1445, "standardize": True},
        "PT59S": {"seconds": 59, "standardize": True},
        "PT1H4M56S": {"minutes": 10, "seconds": 3296, "standardize": True},
    }
    for expression, ctrl_result in test_expressions.items():
        yield expression, ctrl_result


def get_timepoint_dumper_tests():
    """Yield tests for custom timepoint dumps."""
    return [
        (
            {"year": 44, "month_of_year": 1, "day_of_month": 4,
             "hour_of_day": 5, "minute_of_hour": 1, "second_of_minute": 2,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("CCYY-MMDDThhmmZ", "0044-0104T0501Z"),
             ("YYDDDThh:mm:ss", "44004T05:01:02"),
             ("WwwD", "W011"),
             ("CCDDDThh*ss-0600", "00003T23*02-0600"),
             (u"+XCCYY-MM-DDThh:mm:ss-11:45",
              "+000044-01-03T17:16:02-11:45"),
             (u"+XCCYYMM-DDThh-01:00", "+00004401-04T04-01:00"),
             (u"+XCCYYMM-DDThh+13:00", "+00004401-04T18+13:00"),
             (u"+XCCYYMM-DDThh-0100", "+00004401-04T04-0100"),
             (u"+XCCYYMM-DDThh+1300", "+00004401-04T18+1300"),
             (u"+XCCYYMMDDThh-0100", "+0000440104T04-0100"),
             (u"+XCCYYMMDDThh+13", "+0000440104T18+13"),
             (u"+XCCYYMMDDThh+hhmm", "+0000440104T05+0000"),
             (u"+XCCYY-MM-DDThh:mm:ss+hh:mm",
              "+000044-01-04T05:01:02+00:00"),
             ("DD/MM/CCYY is a silly format", "04/01/0044 is a silly format"),
             ("ThhZ", "T05Z"),
             ("%Y-%m-%dT%H:%M", "0044-01-04T05:01")]
        ),
        (
            {"year": 500200, "month_of_year": 7, "day_of_month": 28,
             "expanded_year_digits": 2, "hour_of_day": 0,
             "hour_of_day_decimal": 0.4356, "time_zone_hour": -8,
             "time_zone_minute": -30},
            [("+XCCYY-MMDDThhmmZ", "+500200-0728T0856Z"),
             ("+XCCYYDDDThh:mm:ss", "+500200209T00:26:08"),
             ("WwwD", "W311"),
             ("+XCCDDDThh*ss-0600", "+5002209T02*08-0600"),
             (u"+XCCYY-MM-DDThh:mm:ss-11:45",
              "+500200-07-27T21:11:08-11:45"),
             (u"+XCCYYMM-DDThhmm-01:00", "+50020007-28T0756-01:00"),
             (u"+XCCYYMM-DDThhmm+13:00", "+50020007-28T2156+13:00"),
             (u"+XCCYYMM-DDThhmm-0100", "+50020007-28T0756-0100"),
             (u"+XCCYYMM-DDThhmm+1300", "+50020007-28T2156+1300"),
             (u"+XCCYYMMDDThhmm-0100", "+5002000728T0756-0100"),
             (u"+XCCYYMMDDThhmm+13", "+5002000728T2156+13"),
             (u"+XCCYYMMDDThh+hhmm", "+5002000728T00-0830"),
             (u"+XCCYYWwwDThhmm+hh", "+500200W311T0026-08"),
             (u"+XCCYYDDDThhmm+hh", "+500200209T0026-08"),
             (u"+XCCYY-MM-DDThh:mm:ss+hh:mm",
              "+500200-07-28T00:26:08-08:30"),
             (u"+XCCYY-MM-DDThh:mm:ssZ", "+500200-07-28T08:56:08Z"),
             ("DD/MM/+XCCYY is a silly format", "28/07/+500200 is a silly format"),
             ("ThhmmZ", "T0856Z"),
             ("%m-%dT%H:%M", "07-28T00:26")]
        ),
        (
            {"year": -56, "day_of_year": 318, "expanded_year_digits": 2,
             "hour_of_day": 5, "minute_of_hour": 1, "time_zone_hour": 6},
            [("+XCCYY-MMDDThhmmZ", "-000056-1112T2301Z"),
             ("+XCCYYDDDThh:mm:ss", "-000056318T05:01:00"),
             ("WwwD", "W461"),
             ("+XCCDDDThh*ss-0600", "-0000317T17*00-0600"),
             (u"+XCCYY-MM-DDThh:mm:ss-11:45",
              "-000056-11-12T11:16:00-11:45"),
             (u"+XCCYYMM-DDThhmm-01:00", "-00005611-12T2201-01:00"),
             (u"+XCCYYMM-DDThhmm+13:00", "-00005611-13T1201+13:00"),
             (u"+XCCYYMM-DDThhmm-0100", "-00005611-12T2201-0100"),
             (u"+XCCYYMM-DDThhmm+1300", "-00005611-13T1201+1300"),
             (u"+XCCYYMMDDThhmm-0100", "-0000561112T2201-0100"),
             (u"+XCCYYMMDDThhmm+13", "-0000561113T1201+13"),
             (u"+XCCYYMMDDThh+hhmm", "-0000561113T05+0600"),
             (u"+XCCYYWwwDThhmm+hh", "-000056W461T0501+06"),
             (u"+XCCYYDDDThhmm+hh", "-000056318T0501+06"),
             (u"+XCCYY-MM-DDThh:mm:ss+hh:mm",
              "-000056-11-13T05:01:00+06:00"),
             (u"+XCCYY-MM-DDThh:mm:ssZ", "-000056-11-12T23:01:00Z"),
             ("DD/MM/+XCCYY is a silly format", "13/11/-000056 is a silly format"),
             ("ThhmmZ", "T2301Z"),
             ("%m-%dT%H:%M", "11-13T05:01")]
        ),
        (
            {"year": 1000, "week_of_year": 1, "day_of_week": 1,
             "time_zone_hour": 0},
            [("CCYY-MMDDThhmmZ", "0999-1230T0000Z"),
             ("CCYY-DDDThhmmZ", "0999-364T0000Z"),
             ("CCYY-Www-DThhmm+0200", "1000-W01-1T0200+0200"),
             ("CCYY-Www-DThhmm-0200", "0999-W52-7T2200-0200"),
             ("%Y-%m-%dT%H:%M", "0999-12-30T00:00")]
        ),
        (
            {"year": 999, "day_of_year": 364, "time_zone_hour": 0},
            [("CCYY-MMDDThhmmZ", "0999-1230T0000Z"),
             ("CCYY-DDDThhmmZ", "0999-364T0000Z"),
             ("CCYY-Www-DThhmm+0200", "1000-W01-1T0200+0200"),
             ("CCYY-Www-DThhmm-0200", "0999-W52-7T2200-0200"),
             ("%Y-%m-%dT%H:%M", "0999-12-30T00:00")]
        )
    ]


def get_timepointdumper_failure_tests():
    """Yield tests that raise exceptions for custom time point dumps."""
    bounds_error = dumpers.TimePointDumperBoundsError
    return [
        (
            {"year": 10000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("CCYY-MMDDThhmmZ", bounds_error, 0),
             ("%Y-%m-%dT%H:%M", bounds_error, 0)]
        ),
        (
            {"year": -10000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("CCYY-MMDDThhmmZ", bounds_error, 0),
             ("%Y-%m-%dT%H:%M", bounds_error, 0)]
        ),
        (
            {"year": 10000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("CCYY-MMDDThhmmZ", bounds_error, 2)]
        ),
        (
            {"year": -10000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("CCYY-MMDDThhmmZ", bounds_error, 2)]
        ),
        (
            {"year": 1000000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("+XCCYY-MMDDThhmmZ", bounds_error, 2)]
        ),
        (
            {"year": -1000000, "month_of_year": 1, "day_of_month": 4,
             "time_zone_hour": 0, "time_zone_minute": 0},
            [("+XCCYY-MMDDThhmmZ", bounds_error, 2)]
        )
    ]


def get_timepointparser_tests(allow_only_basic=False,
                              allow_truncated=False,
                              skip_time_zones=False):
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
    test_time_zone_map = {
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
        time_zone_format_tests = test_time_zone_map[format_type]
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
                        if skip_time_zones:
                            continue
                        time_zone_items = time_zone_format_tests.items()
                        for time_zone_expr, time_zone_info in time_zone_items:
                            tz_expr = combo_expr + time_zone_expr
                            tz_info = {}
                            for key, value in (combo_info.items() +
                                                time_zone_info.items()):
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
                if skip_time_zones:
                    continue
                time_zone_items = time_zone_format_tests.items()
                for time_zone_expr, time_zone_info in time_zone_items:
                    tz_expr = combo_expr + time_zone_expr
                    tz_info = {}
                    for key, value in (combo_info.items() +
                                        time_zone_info.items()):
                        tz_info[key] = value
                    yield tz_expr, tz_info


def get_timerecurrence_expansion_tests():
    """Return test expansion expressions for data.TimeRecurrence."""
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
         ["-100024-02-10T17:00:00-12:30", "-100024-02-10T22:30:00-12:30",
          "-100024-02-11T04:00:00-12:30"])
    ]


def get_timerecurrence_expansion_tests_for_alt_calendar(calendar_mode):
    """Return alternate calendar tests for data.TimeRecurrence."""
    if calendar_mode == "360":
        return get_timerecurrence_expansion_tests_360()
    if calendar_mode == "365":
        return get_timerecurrence_expansion_tests_365()
    if calendar_mode == "366":
        return get_timerecurrence_expansion_tests_366()


def get_timerecurrence_expansion_tests_360():
    """Return test expansion expressions for data.TimeRecurrence."""
    return [
        ("R13/1984-01-30T00Z/P1M",
         ["1984-01-30T00:00:00Z", "1984-02-30T00:00:00Z", "1984-03-30T00:00:00Z", 
          "1984-04-30T00:00:00Z", "1984-05-30T00:00:00Z", "1984-06-30T00:00:00Z",
          "1984-07-30T00:00:00Z", "1984-08-30T00:00:00Z", "1984-09-30T00:00:00Z",
          "1984-10-30T00:00:00Z", "1984-11-30T00:00:00Z", "1984-12-30T00:00:00Z",
          "1985-01-30T00:00:00Z"]),
        ("R2/1984-01-30T00Z/P1D",
         ["1984-01-30T00:00:00Z", "1984-02-01T00:00:00Z"]),
        ("R2/P1D/1984-02-01T00Z",
         ["1984-01-30T00:00:00Z", "1984-02-01T00:00:00Z"]),
        ("R2/P1D/1984-01-01T00Z",
         ["1983-12-30T00:00:00Z", "1984-01-01T00:00:00Z"]),
        ("R2/1983-12-30T00Z/P1D",
         ["1983-12-30T00:00:00Z", "1984-01-01T00:00:00Z"]),
        ("R2/P1D/2005-01-01T00Z",
         ["2004-12-30T00:00:00Z", "2005-01-01T00:00:00Z"]),
        ("R2/2003-12-30T00Z/P1D",
         ["2003-12-30T00:00:00Z", "2004-01-01T00:00:00Z"]),
        ("R2/P1D/2004-01-01T00Z",
         ["2003-12-30T00:00:00Z", "2004-01-01T00:00:00Z"]),
        ("R2/2004-12-30T00Z/P1D",
         ["2004-12-30T00:00:00Z", "2005-01-01T00:00:00Z"]),
        ("R3/P1Y/2005-02-30T00Z",
         ["2003-02-30T00:00:00Z", "2004-02-30T00:00:00Z", "2005-02-30T00:00:00Z"]),
        ("R3/2003-02-30T00Z/P1Y",
         ["2003-02-30T00:00:00Z", "2004-02-30T00:00:00Z", "2005-02-30T00:00:00Z"]),
    ]


def get_timerecurrence_expansion_tests_365():
    """Return test expansion expressions for data.TimeRecurrence."""
    return [
        ("R13/1984-01-30T00Z/P1M",
         ["1984-01-30T00:00:00Z", "1984-02-28T00:00:00Z",
          "1984-03-28T00:00:00Z", "1984-04-28T00:00:00Z",
          "1984-05-28T00:00:00Z", "1984-06-28T00:00:00Z",
          "1984-07-28T00:00:00Z", "1984-08-28T00:00:00Z",
          "1984-09-28T00:00:00Z", "1984-10-28T00:00:00Z",
          "1984-11-28T00:00:00Z", "1984-12-28T00:00:00Z",
          "1985-01-28T00:00:00Z"]),
        ("R13/1985-01-30T00Z/P1M",
         ["1985-01-30T00:00:00Z", "1985-02-28T00:00:00Z",
          "1985-03-28T00:00:00Z", "1985-04-28T00:00:00Z",
          "1985-05-28T00:00:00Z", "1985-06-28T00:00:00Z",
          "1985-07-28T00:00:00Z", "1985-08-28T00:00:00Z",
          "1985-09-28T00:00:00Z", "1985-10-28T00:00:00Z",
          "1985-11-28T00:00:00Z", "1985-12-28T00:00:00Z",
          "1986-01-28T00:00:00Z"]),
        ("R2/1984-01-30T00Z/P1D",
         ["1984-01-30T00:00:00Z", "1984-01-31T00:00:00Z"]),
        ("R2/P1D/1984-02-01T00Z",
         ["1984-01-31T00:00:00Z", "1984-02-01T00:00:00Z"]),
        ("R2/P1D/1984-01-01T00Z",
         ["1983-12-31T00:00:00Z", "1984-01-01T00:00:00Z"]),
        ("R2/1983-12-30T00Z/P1D",
         ["1983-12-30T00:00:00Z", "1983-12-31T00:00:00Z"]),
        ("R2/2000-02-28T00Z/P1Y1D",
         ["2000-02-28T00:00:00Z", "2001-03-01T00:00:00Z"]),
        ("R2/2001-02-28T00Z/P1Y1D",
         ["2001-02-28T00:00:00Z", "2002-03-01T00:00:00Z"]),
    ]


def get_timerecurrence_expansion_tests_366():
    """Return test expansion expressions for data.TimeRecurrence."""
    return [
        ("R13/1984-01-30T00Z/P1M",
         ["1984-01-30T00:00:00Z", "1984-02-29T00:00:00Z",
          "1984-03-29T00:00:00Z", "1984-04-29T00:00:00Z",
          "1984-05-29T00:00:00Z", "1984-06-29T00:00:00Z",
          "1984-07-29T00:00:00Z", "1984-08-29T00:00:00Z",
          "1984-09-29T00:00:00Z", "1984-10-29T00:00:00Z",
          "1984-11-29T00:00:00Z", "1984-12-29T00:00:00Z",
          "1985-01-29T00:00:00Z"]),
        ("R13/1985-01-30T00Z/P1M",
         ["1985-01-30T00:00:00Z", "1985-02-29T00:00:00Z",
          "1985-03-29T00:00:00Z", "1985-04-29T00:00:00Z",
          "1985-05-29T00:00:00Z", "1985-06-29T00:00:00Z",
          "1985-07-29T00:00:00Z", "1985-08-29T00:00:00Z",
          "1985-09-29T00:00:00Z", "1985-10-29T00:00:00Z",
          "1985-11-29T00:00:00Z", "1985-12-29T00:00:00Z",
          "1986-01-29T00:00:00Z"]),
        ("R2/1984-01-30T00Z/P1D",
         ["1984-01-30T00:00:00Z", "1984-01-31T00:00:00Z"]),
        ("R2/P1D/1984-02-01T00Z",
         ["1984-01-31T00:00:00Z", "1984-02-01T00:00:00Z"]),
        ("R2/P1D/1984-01-01T00Z",
         ["1983-12-31T00:00:00Z", "1984-01-01T00:00:00Z"]),
        ("R2/1983-12-30T00Z/P1D",
         ["1983-12-30T00:00:00Z", "1983-12-31T00:00:00Z"]),
        ("R2/1999-02-28T00Z/P1Y1D",
         ["1999-02-28T00:00:00Z", "2000-02-29T00:00:00Z"]),
        ("R2/2000-02-28T00Z/P1Y1D",
         ["2000-02-28T00:00:00Z", "2001-02-29T00:00:00Z"]),
        ("R2/2001-02-28T00Z/P1Y1D",
         ["2001-02-28T00:00:00Z", "2002-02-29T00:00:00Z"]),
    ]


def get_timerecurrence_membership_tests():
    """Return test membership expressions for data.TimeRecurrence."""
    return [
        ("R3/1001-W01-1T00:00:00Z/1002-W52-6T00:00:00-05:30",
         [("1001-W01-1T00:00:00Z", True),
          ("1000-12-29T00:00:00Z", True),
          ("0901-07-08T12:45:00Z", False),
          ("1001-W01-2T00:00:00Z", False),
          ("1001-W53-3T14:45:00Z", True),
          ("1002-W52-6T05:30:00Z", True),
          ("1002-W52-6T03:30:00-02:00", True),
          ("1002-W52-6T07:30:00+02:00", True),
          ("10030101T00Z", False)]),
        ("R3/P700D/1957-W01-1T06,5Z",
         [("1953-W10-1T06,5Z", True),
          ("1953-03-02T06,5Z", True),
          ("1952-03-02T06,5Z", False),
          ("1955-W05-1T06,5Z", True),
          ("1957-W01-1T06,5Z", True),
          ("1956-366T06,5Z", True),
          ("1956-356T04,5Z", False)]),
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
        duration_parser = parsers.DurationParser()
        for point_expr in test_points:
            duration_tests = get_timedurationparser_tests()
            start_point = point_parser.parse(point_expr)
            for duration_expr, duration_result in duration_tests:
                if duration_expr.startswith("-P"):
                    # Our negative durations are not supported in recurrences.
                    continue
                duration = duration_parser.parse(duration_expr)
                end_point = start_point + duration
                if reps is not None:
                    expr_1 = ("R" + reps_string + "/" + str(start_point) +
                                "/" + str(end_point))
                    yield expr_1, {"repetitions": reps,
                                    "start_point": start_point,
                                    "end_point": end_point}
                expr_3 = ("R" + reps_string + "/" + str(start_point) +
                            "/" + str(duration))
                yield expr_3, {"repetitions": reps,
                                "start_point": start_point,
                                "duration": duration}
                expr_4 = ("R" + reps_string + "/" + str(duration) + "/" +
                            str(end_point))
                yield expr_4, {"repetitions": reps, "duration": duration,
                                "end_point": end_point}


def get_local_time_zone_hours_minutes():
    """Provide an independent method of getting the local time zone."""
    import datetime
    utc_offset = datetime.datetime.now() - datetime.datetime.utcnow()
    utc_offset_hours = (utc_offset.seconds + 1800) // 3600
    utc_offset_minutes = (
        ((utc_offset.seconds - 3600 * utc_offset_hours) + 30) // 60
    )
    return utc_offset_hours, utc_offset_minutes


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

    def test_days_in_year_range(self):
        """Test the summing-over-days-in-year-range shortcut code."""
        for start_year in range(-401, 2):
            for end_year in range(start_year, 2):
               test_days = data.get_days_in_year_range(
                   start_year, end_year)
               control_days = 0
               for year in xrange(start_year, end_year + 1):
                   control_days += data.get_days_in_year(year)
               self.assertEqual(
                   control_days, test_days, "days in %s to %s" % (
                       start_year, end_year)
               )

    def test_timeduration(self):
        """Test the duration class methods."""
        for test_props, method, method_args, ctrl_results in (
                get_timeduration_tests()):
            duration = data.Duration(**test_props)
            duration_method = getattr(duration, method)
            test_results = duration_method(*method_args)
            self.assertEqual(
                test_results, ctrl_results,
                "%s -> %s(%s)" % (test_props, method, method_args)
            )

    def test_timeduration_parser(self):
        """Test the duration parsing."""
        parser = parsers.DurationParser()
        for expression, ctrl_result in get_timedurationparser_tests():
            try:
                test_result = str(parser.parse(expression))
            except parsers.ISO8601SyntaxError:
                raise ValueError(
                    "DurationParser test failed to parse '%s'" %
                    expression
                )
            self.assertEqual(test_result, ctrl_result, expression)

    def test_timeduration_dumper(self):
        """Test the duration dumping."""
        for ctrl_expression, test_props in get_timedurationdumper_tests():
            duration = data.Duration(**test_props)
            test_expression = str(duration)
            self.assertEqual(test_expression, ctrl_expression,
                             str(test_props))

    def test_timepoint(self):
        """Test the time point data model (takes a while)."""
        pool = multiprocessing.Pool(processes=4)
        pool.map_async(test_timepoint_at_year, range(1801, 2403)).get()

    def test_timepoint_plus_float_time_duration_day_of_month_type(self):
        """Test (TimePoint + Duration).day_of_month is an int."""
        time_point = data.TimePoint(year=2000) + data.Duration(seconds=1.0)
        self.assertEqual(type(time_point.day_of_month), int)

    def test_timepoint_time_zone(self):
        """Test the time zone handling of timepoint instances."""
        year = 2000
        month_of_year = 1
        day_of_month = 1
        utc_offset_hours, utc_offset_minutes = (
            get_local_time_zone_hours_minutes()
        )
        for hour_of_day in range(24):
            for minute_of_hour in [0, 30]:
                test_dates = [
                    data.TimePoint(
                        year=year,
                        month_of_year=month_of_year,
                        day_of_month=day_of_month,
                        hour_of_day=hour_of_day,
                        minute_of_hour=minute_of_hour
                    )
                ]
                test_dates.append(test_dates[0].copy())
                test_dates.append(test_dates[0].copy())
                test_dates.append(test_dates[0].copy())
                test_dates[0].set_time_zone_to_utc()
                self.assertEqual(test_dates[0].time_zone.hours, 0,
                                 test_dates[0])
                self.assertEqual(test_dates[0].time_zone.minutes, 0,
                                 test_dates[0])
                test_dates[1].set_time_zone_to_local()
                self.assertEqual(test_dates[1].time_zone.hours,
                                 utc_offset_hours, test_dates[1])
                
                self.assertEqual(test_dates[1].time_zone.minutes,
                                 utc_offset_minutes, test_dates[1])
                test_dates[2].set_time_zone(
                    data.TimeZone(hours=-13, minutes=-45))
                
                test_dates[3].set_time_zone(
                    data.TimeZone(hours=8, minutes=30))
                for i in range(len(test_dates)):
                    i_date_str = str(test_dates[i])
                    date_no_tz = test_dates[i].copy()
                    date_no_tz.time_zone = data.TimeZone(hours=0, minutes=0)

                    # TODO: https://github.com/metomi/isodatetime/issues/34.
                    if (test_dates[i].time_zone.hours >= 0 or
                        test_dates[i].time_zone.minutes >= 0):
                        utc_offset = date_no_tz - test_dates[i]
                    else:
                        utc_offset = (test_dates[i] - date_no_tz) * -1

                    self.assertEqual(utc_offset.hours,
                                     test_dates[i].time_zone.hours,
                                     i_date_str + " utc offset (hrs)")
                    self.assertEqual(utc_offset.minutes,
                                     test_dates[i].time_zone.minutes,
                                     i_date_str + " utc offset (mins)")       
                    for j in range(len(test_dates)):
                        j_date_str = str(test_dates[j])
                        self.assertEqual(
                            test_dates[i], test_dates[j],
                            i_date_str + " == " + j_date_str
                        )
                        duration = test_dates[j] - test_dates[i]
                        self.assertEqual(
                            duration, data.Duration(days=0),
                            i_date_str + " - " + j_date_str
                        )

    def test_timepoint_dumper(self):
        """Test the dumping of TimePoint instances."""
        parser = parsers.TimePointParser(allow_truncated=True,
                                         default_to_unknown_time_zone=True)
        dumper = dumpers.TimePointDumper()
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True):
            ctrl_timepoint = data.TimePoint(**timepoint_kwargs)
            try:
                test_timepoint = parser.parse(str(ctrl_timepoint))
            except parsers.ISO8601SyntaxError as syn_exc:
                raise ValueError(
                    "Parsing failed for the dump of {0}: {1}".format(
                        expression, syn_exc))
            self.assertEqual(test_timepoint,
                             ctrl_timepoint, expression)
        for timepoint_kwargs, format_results in (
                get_timepoint_dumper_tests()):
            ctrl_timepoint = data.TimePoint(**timepoint_kwargs)
            for format_, ctrl_data in format_results:
                test_data = dumper.dump(ctrl_timepoint, format_)
                self.assertEqual(test_data, ctrl_data, format_)
        for timepoint_kwargs, format_exception_results in (
                get_timepointdumper_failure_tests()):
            ctrl_timepoint = data.TimePoint(**timepoint_kwargs)
            for format_, ctrl_exception, num_expanded_year_digits in (
                    format_exception_results):
                dumper = dumpers.TimePointDumper(
                    num_expanded_year_digits=num_expanded_year_digits)
                self.assertRaises(ctrl_exception, dumper.dump,
                                  ctrl_timepoint, format_)

    def test_timepoint_parser(self):
        """Test the parsing of date/time expressions."""

        # Test unknown time zone assumptions.
        parser = parsers.TimePointParser(
            allow_truncated=True,
            default_to_unknown_time_zone=True)
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True):
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_data = str(parser.parse(expression))
            except parsers.ISO8601SyntaxError as syn_exc:
                raise ValueError("Parsing failed for {0}: {1}".format(
                   expression, syn_exc))
            ctrl_data = str(data.TimePoint(**timepoint_kwargs))
            self.assertEqual(test_data, ctrl_data, expression)
            ctrl_data = expression
            test_data = str(parser.parse(expression, dump_as_parsed=True))
            self.assertEqual(test_data, ctrl_data, expression)

        # Test local time zone assumptions (the default).
        utc_offset_hours, utc_offset_minutes = (
            get_local_time_zone_hours_minutes()
        )
        parser = parsers.TimePointParser(allow_truncated=True)
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True, skip_time_zones=True):
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_timepoint = parser.parse(expression)
            except parsers.ISO8601SyntaxError as syn_exc:
                raise ValueError("Parsing failed for {0}: {1}".format(
                   expression, syn_exc))
            test_data = (test_timepoint.time_zone.hours,
                         test_timepoint.time_zone.minutes)
            ctrl_data = (utc_offset_hours, utc_offset_minutes)
            self.assertEqual(test_data, ctrl_data,
                             "Local time zone for " + expression)

        # Test given time zone assumptions.
        utc_offset_hours, utc_offset_minutes = (
            get_local_time_zone_hours_minutes()
        )
        given_utc_offset_hours = -2  # This is an arbitrary number!
        if given_utc_offset_hours == utc_offset_hours:
            # No point testing this twice, change it.
            given_utc_offset_hours = -3
        given_utc_offset_minutes = -15
        given_time_zone_hours_minutes = (
            given_utc_offset_hours, given_utc_offset_minutes)
        parser = parsers.TimePointParser(
            allow_truncated=True,
            assumed_time_zone=given_time_zone_hours_minutes
        )
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True, skip_time_zones=True):
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_timepoint = parser.parse(expression)
            except parsers.ISO8601SyntaxError as syn_exc:
                raise ValueError("Parsing failed for {0}: {1}".format(
                   expression, syn_exc))
            test_data = (test_timepoint.time_zone.hours,
                         test_timepoint.time_zone.minutes)
            ctrl_data = given_time_zone_hours_minutes
            self.assertEqual(test_data, ctrl_data,
                             "A given time zone for " + expression)

        # Test UTC time zone assumptions.
        parser = parsers.TimePointParser(
            allow_truncated=True,
            assumed_time_zone=(0, 0)
        )
        for expression, timepoint_kwargs in get_timepointparser_tests(
                allow_truncated=True, skip_time_zones=True):
            timepoint_kwargs = copy.deepcopy(timepoint_kwargs)
            try:
                test_timepoint = parser.parse(expression)
            except parsers.ISO8601SyntaxError as syn_exc:
                raise ValueError("Parsing failed for {0}: {1}".format(
                   expression, syn_exc))
            test_data = (test_timepoint.time_zone.hours,
                         test_timepoint.time_zone.minutes)
            ctrl_data = (0, 0)
            self.assertEqual(test_data, ctrl_data,
                             "UTC for " + expression)

    def test_timepoint_strftime_strptime(self):
        """Test the strftime/strptime for date/time expressions."""
        import datetime
        parser = parsers.TimePointParser()
        parse_tokens = parser_spec.STRFTIME_TRANSLATE_INFO.keys()
        parse_tokens.remove("%z")  # Don't test datetime's tz handling.
        format_string = ""
        for i, token in enumerate(parse_tokens):
            format_string += token
            if i % 2 == 0:
                format_string += " "
            if i % 3 == 0:
                format_string += ":"
            if i % 5 == 0:
                format_string += "?foobar"
            if i % 7 == 0:
                format_string += "++("
        strftime_string = format_string
        strptime_strings = [format_string]
        for key in parser_spec.STRPTIME_EXCLUSIVE_GROUP_INFO.keys():
            strptime_strings[-1] = strptime_strings[-1].replace(key, "")
        strptime_strings.append(format_string)
        for values in parser_spec.STRPTIME_EXCLUSIVE_GROUP_INFO.values():
            for value in values:
                strptime_strings[-1] = strptime_strings[-1].replace(value, "")
        ctrl_date = datetime.datetime(2002, 3, 1, 12, 30, 2)

        # Test %z dumping.
        for sign in [1, -1]:
            for hour in range(0, 24):
                for minute in range(0, 59):
                    if hour == 0 and minute == 0 and sign == -1:
                        # -0000, same as +0000, but invalid.
                        continue
                    test_date = data.TimePoint(
                        year=ctrl_date.year,
                        month_of_year=ctrl_date.month,
                        day_of_month=ctrl_date.day,
                        hour_of_day=ctrl_date.hour,
                        minute_of_hour=ctrl_date.minute,
                        second_of_minute=ctrl_date.second,
                        time_zone_hour=sign * hour,
                        time_zone_minute=sign * minute
                    )
                    ctrl_string = "-" if sign == -1 else "+"
                    ctrl_string += "%02d%02d" % (hour, minute)
                    self.assertEqual(test_date.strftime("%z"),
                                     ctrl_string,
                                     "%z for " + str(test_date))       

        test_date = data.TimePoint(
            year=ctrl_date.year,
            month_of_year=ctrl_date.month,
            day_of_month=ctrl_date.day,
            hour_of_day=ctrl_date.hour,
            minute_of_hour=ctrl_date.minute,
            second_of_minute=ctrl_date.second
        )
        for test_date in [test_date, test_date.copy().to_week_date(),
                          test_date.copy().to_ordinal_date()]:
            ctrl_data = ctrl_date.strftime(strftime_string)
            test_data = test_date.strftime(strftime_string)
            self.assertEqual(test_data, ctrl_data, strftime_string)
            for strptime_string in strptime_strings:
                ctrl_dump = ctrl_date.strftime(strptime_string)
                test_dump = test_date.strftime(strptime_string)
                self.assertEqual(test_dump, ctrl_dump, strptime_string)
                if "%s" in strptime_string:
                    # The datetime library can't handle this for strptime!
                    ctrl_data = ctrl_date
                else:
                    ctrl_data = datetime.datetime.strptime(
                        ctrl_dump, strptime_string)
                test_data = parser.strptime(test_dump, strptime_string)
                
                ctrl_data = (
                    ctrl_data.year, ctrl_data.month, ctrl_data.day,
                    ctrl_data.hour, ctrl_data.minute, ctrl_data.second
                )
                test_data = tuple(list(test_data.get_calendar_date()) +
                                  list(test_data.get_hour_minute_second()))
                if "%y" in strptime_string:
                    # %y is the decadal year (00 to 99) within a century.
                    # The datetime library, for some reason, sets a default
                    # century of '2000' - so nuke this extra information.
                    ctrl_data = tuple([ctrl_data[0] % 100] +
                                      list(ctrl_data[1:]))
                self.assertEqual(test_data, ctrl_data, test_dump + "\n" +
                                 strptime_string)

    def test_timerecurrence_alt_calendars(self):
        """Test recurring date/time series for alternate calendars."""
        for calendar_mode in ["360", "365", "366"]:
            data.CALENDAR.set_mode(calendar_mode + "day")
            self.assertEqual(
                data.CALENDAR.mode,
                getattr(data.Calendar, "MODE_%s" % calendar_mode)
            )
            parser = parsers.TimeRecurrenceParser()
            tests = get_timerecurrence_expansion_tests_for_alt_calendar(
                calendar_mode)
            for expression, ctrl_results in tests:
                try:
                    test_recurrence = parser.parse(expression)
                except parsers.ISO8601SyntaxError:
                    raise ValueError(
                        "TimeRecurrenceParser test failed to parse '%s'" %
                        expression
                    )
                test_results = []
                for i, time_point in enumerate(test_recurrence):
                    test_results.append(str(time_point))
                self.assertEqual(test_results, ctrl_results,
                                 expression + "(%s)" % calendar_mode)
            data.CALENDAR.set_mode()
            self.assertEqual(data.CALENDAR.mode,
                             data.Calendar.MODE_GREGORIAN)

    def test_timerecurrence(self):
        """Test the recurring date/time series data model."""
        parser = parsers.TimeRecurrenceParser()
        for expression, ctrl_results in get_timerecurrence_expansion_tests():
            try:
                test_recurrence = parser.parse(expression)
            except parsers.ISO8601SyntaxError:
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
            if test_recurrence.start_point is None:
                forward_method = test_recurrence.get_prev
                backward_method = test_recurrence.get_next
            else:
                forward_method = test_recurrence.get_next
                backward_method = test_recurrence.get_prev
            test_points = [test_recurrence[0]]
            test_points.append(forward_method(test_points[-1]))
            test_points.append(forward_method(test_points[-1]))
            test_results = [str(point) for point in test_points]
            self.assertEqual(test_results, ctrl_results, expression)
            if test_recurrence[2] is not None:
                test_points = [test_recurrence[2]]
                test_points.append(backward_method(test_points[-1]))
                test_points.append(backward_method(test_points[-1]))
                test_points.append(backward_method(test_points[-1]))
            self.assertEqual(test_points[3], None, expression)
            test_points.pop(3)
            test_points.reverse()
            test_results = [str(point) for point in test_points]
            self.assertEqual(test_results, ctrl_results, expression)
            
        for expression, results in get_timerecurrence_membership_tests():
            try:
                test_recurrence = parser.parse(expression)
            except parsers.ISO8601SyntaxError:
                raise ValueError(
                    "TimeRecurrenceParser test failed to parse '%s'" %
                    expression
                )
            for timepoint_expression, ctrl_is_member in results:
                timepoint = parsers.parse_timepoint_expression(
                    timepoint_expression)
                test_is_member = test_recurrence.get_is_valid(timepoint)
                self.assertEqual(test_is_member, ctrl_is_member,
                                 timepoint_expression + " in " + expression)

    def test_timerecurrence_parser(self):
        """Test the recurring date/time series parsing."""
        parser = parsers.TimeRecurrenceParser()
        for expression, test_info in get_timerecurrenceparser_tests():
            try:
                test_data = str(parser.parse(expression))
            except parsers.ISO8601SyntaxError:
                raise ValueError("Parsing failed for %s" % expression)
            ctrl_data = str(data.TimeRecurrence(**test_info))
            self.assertEqual(test_data, ctrl_data, expression)


def assert_equal(data1, data2):
    """A function-level equivalent of the unittest method."""
    assert data1 == data2


def test_timepoint_at_year(test_year):
    """Test the TimePoint and Calendar data model over a given year."""
    import datetime
    import random
    my_date = datetime.datetime(test_year, 1, 1)
    stop_date = datetime.datetime(test_year + 1, 1, 1)
    test_duration_attributes = [
        ("weeks", 110),
        ("days", 770),
        ("hours", 770*24),
        ("minutes", 770 * 24 * 60),
        ("seconds", 770 * 24 * 60 * 60)
    ]
    while my_date <= stop_date:
        ctrl_data = my_date.isocalendar()
        test_date = data.TimePoint(
            year=my_date.year,
            month_of_year=my_date.month,
            day_of_month=my_date.day
        )
        test_week_date = test_date.to_week_date()
        test_data = test_week_date.get_week_date()
        assert_equal(test_data, ctrl_data)
        ctrl_data = (my_date.year, my_date.month, my_date.day)
        test_data = test_week_date.get_calendar_date()
        assert_equal(test_data, ctrl_data)
        ctrl_data = my_date.toordinal()
        year, day_of_year = test_date.get_ordinal_date()
        test_data = day_of_year
        test_data += data.get_days_since_1_ad(year - 1)
        assert_equal(test_data, ctrl_data)
        for attribute, attr_max in test_duration_attributes:
            delta_attr = random.randrange(0, attr_max)
            kwargs = {attribute: delta_attr}
            ctrl_data = my_date + datetime.timedelta(**kwargs)
            ctrl_data = (ctrl_data.year, ctrl_data.month, ctrl_data.day)
            test_data = (
                test_date + data.Duration(
                    **kwargs)).get_calendar_date()
            assert_equal(test_data, ctrl_data)
            ctrl_data = (my_date - datetime.timedelta(**kwargs))
            ctrl_data = (ctrl_data.year, ctrl_data.month, ctrl_data.day)
            test_data = (
                test_date - data.Duration(
                    **kwargs)).get_calendar_date()
            assert_equal(test_data, ctrl_data)
        kwargs = {}
        for attribute, attr_max in test_duration_attributes:
            delta_attr = random.randrange(0, attr_max)
            kwargs[attribute] = delta_attr
        test_date_minus = (
            test_date - data.Duration(**kwargs))
        test_data = test_date - test_date_minus
        ctrl_data = data.Duration(**kwargs)
        assert_equal(test_data, ctrl_data)
        test_data = (test_date_minus + (test_date - test_date_minus))
        ctrl_data = test_date
        assert_equal(test_data, ctrl_data)
        test_data = (test_date_minus + data.Duration(**kwargs))
        ctrl_data = test_date
        assert_equal(test_data, ctrl_data)
        ctrl_data = (my_date + datetime.timedelta(minutes=450) +
                        datetime.timedelta(hours=5) -
                        datetime.timedelta(seconds=500, weeks=5))
        ctrl_data = [(ctrl_data.year, ctrl_data.month, ctrl_data.day),
                        (ctrl_data.hour, ctrl_data.minute, ctrl_data.second)]
        test_data = (
            test_date + data.Duration(minutes=450) +
            data.Duration(hours=5) -
            data.Duration(weeks=5, seconds=500)
        )
        test_data = [test_data.get_calendar_date(),
                        test_data.get_hour_minute_second()]
        assert_equal(test_data, ctrl_data)
        timedelta = datetime.timedelta(days=1)
        my_date += timedelta


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSuite)
    unittest.TextTestRunner(verbosity=2).run(suite)
