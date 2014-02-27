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

"""This provides data to drive ISO 8601 parsing functionality."""


DATE_EXPRESSIONS = {
    "basic": {
        "complete": u"""
CCYYMMDD
±XCCYYMMDD
CCYYDDD
±XCCYYDDD
CCYYWwwD
±XCCYYWwwD""",
        "reduced": u"""
CCYY-MM       # Deviation? Not clear if "basic" or "extended" in standard.
CCYY
CC
±XCCYY-MM     # Deviation? Not clear if "basic" or "extended" in standard.
±XCCYY
±XCC
CCYYWww
±XCCYYWww""",
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
-zWwwD
-zWww
-WwwD
-Www
-W-D
"""    },
    "extended": {
        "complete": u"""
CCYY-MM-DD
±XCCYY-MM-DD
CCYY-DDD
±XCCYY-DDD
CCYY-Www-D
±XCCYY-Www-D""",
        "reduced": u"""
CCYY-MM
±XCCYY-MM
CCYY-Www
±XCCYY-Www""",
        "truncated": u"""
-YY-MM
--MM-DD
YY-MM-DD
YY-DDD
-DDD          # Deviation from standard ?
YY-Www-D
YY-Www
-z-WwwD
-z-Www
-Www-D
"""    }
}
TIME_EXPRESSIONS = {
    "basic": {
        "complete": u"""
# No Time Zone
hhmmss

# No Time Zone - decimals
hhmmss,tt
hhmm,nn
hh,ii
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
-mmss,tt
-mm,nn
--ss,tt
"""    },
    "extended": {
        "complete": u"""
# No Time Zone
hh:mm:ss

# No Time Zone - decimals
hh:mm:ss,tt
hh:mm,nn
hh,ii          # Deviation? Not allowed in standard ?
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
-mm:ss,tt
-mm,nn          # Deviation? Not allowed in standard ?
--ss,tt         # Deviation? Not allowed in standard ?
"""    }
}
TIMEZONE_EXPRESSIONS = {
    "basic": u"""
Z
±hh
±hhmm
""",
    "extended": u"""
Z
±hh             # Deviation? Not allowed in standard?
±hh:mm
"""
}
TIME_DESIGNATOR = "T"
_DATE_TRANSLATE_INFO = [
    (u"±", "(?P<year_sign>[-+])",
     "%(year_sign)s", "year_sign"),
    (u"CC", "(?P<century>\d\d)",
     "%(century)02d", "century"),
    (u"YY", "(?P<year_of_century>\d\d)",
     "%(year_of_century)02d", "year_of_century"),
    (u"MM", "(?P<month_of_year>\d\d)",
     "%(month_of_year)02d", "month_of_year"),
    (u"DDD", "(?P<day_of_year>\d\d\d)",
     "%(day_of_year)03d", "day_of_year"),
    (u"DD", "(?P<day_of_month>\d\d)",
     "%(day_of_month)02d", "day_of_month"),
    (u"Www", "W(?P<week_of_year>\d\d)",
     "W%(week_of_year)02d", "week_of_year"),
    (u"D", "(?P<day_of_week>\d)",
     "%(day_of_week)01d", "day_of_week"),
    (u"z", "(?P<year_of_decade>\d)",
     "%(year_of_decade)01d", "year_of_decade"),
    (u"^---", "(?P<truncated>---)",
     "---", None),
    (u"^--", "(?P<truncated>--)",
     "--", None),
    (u"^-", "(?P<truncated>-)",
     "-", None)
]
_TIME_TRANSLATE_INFO = [
    (u"(?<=^hh)mm", "(?P<minute_of_hour>\d\d)",
     "%(minute_of_hour)02d", "minute_of_hour"),
    (u"(?<=^hh:)mm", "(?P<minute_of_hour>\d\d)",
     "%(minute_of_hour)02d", "minute_of_hour"),
    (u"(?<=^-)mm", "(?P<minute_of_hour>\d\d)",
     "%(minute_of_hour)02d", "minute_of_hour"),
    (u"^hh", "(?P<hour_of_day>\d\d)",
     "%(hour_of_day)02d", "hour_of_day"),
    (u",ii", "[,.](?P<hour_of_day_decimal>\d+)",
     "%(hour_of_day_decimal_string)s", "hour_of_day_decimal_string"),
    (u",nn", "[,.](?P<minute_of_hour_decimal>\d+)",
     "%(minute_of_hour_decimal_string)s", "minute_of_hour_decimal_string"),
    (u"ss", "(?P<second_of_minute>\d\d)",
     "%(second_of_minute)02d", "second_of_minute"),
    (u",tt", "[,.](?P<second_of_minute_decimal>\d+)",
     "%(second_of_minute_decimal_string)s",
     "second_of_minute_decimal_string"),
    (u"^--", "(?P<truncated>--)",
     "--", None),
    (u"^-", "(?P<truncated>-)",
     "-", None)
]
_TIMEZONE_TRANSLATE_INFO = [
    (u"(?<=±hh)mm", "(?P<time_zone_minute>\d\d)",
     "%(time_zone_minute_abs)02d", "time_zone_minute_abs"),
    (u"(?<=±hh:)mm", "(?P<time_zone_minute>\d\d)",
     "%(time_zone_minute_abs)02d", "time_zone_minute_abs"),
    (u"(?<=±)hh", "(?P<time_zone_hour>\d\d)",
     "%(time_zone_hour_abs)02d", "time_zone_hour_abs"),
    (u"±", "(?P<time_zone_sign>[-+])",
     "%(time_zone_sign)s", "time_zone_sign"),
    (u"Z", "(?P<time_zone_utc>Z)",
     "Z", None)
]


def get_date_translate_info(num_expanded_year_digits=2):
    expanded_year_digit_regex = "\d" * num_expanded_year_digits
    return _DATE_TRANSLATE_INFO + [
        (u"X",
         "(?P<expanded_year>" + expanded_year_digit_regex + ")",
         "%(expanded_year_digits)0" + str(num_expanded_year_digits) + "d",
         "expanded_year_digits")
    ]


def get_time_translate_info():
    return _TIME_TRANSLATE_INFO


def get_timezone_translate_info():
    return _TIMEZONE_TRANSLATE_INFO

