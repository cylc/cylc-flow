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

import re
from . import timezone


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
hhmmss.tt
hhmm.nn
hh.ii
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
-mmss.tt
-mm.nn
--ss.tt
"""    },
    "extended": {
        "complete": u"""
# No Time Zone
hh:mm:ss

# No Time Zone - decimals
hh:mm:ss,tt
hh:mm,nn
hh,ii          # Deviation? Not allowed in standard ?
hh:mm:ss.tt
hh:mm.nn
hh.ii          # Deviation? Not allowed in standard ?
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
-mm:ss.tt
-mm.nn          # Deviation? Not allowed in standard ?
--ss.tt         # Deviation? Not allowed in standard ?
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
    (u",ii", ",(?P<hour_of_day_decimal>\d+)",
     ",%(hour_of_day_decimal_string)s", "hour_of_day_decimal_string"),
    (u"\.ii", "\.(?P<hour_of_day_decimal>\d+)",
     ".%(hour_of_day_decimal_string)s", "hour_of_day_decimal_string"),
    (u",nn", ",(?P<minute_of_hour_decimal>\d+)",
     ",%(minute_of_hour_decimal_string)s", "minute_of_hour_decimal_string"),
    (u"\.nn", "\.(?P<minute_of_hour_decimal>\d+)",
     ".%(minute_of_hour_decimal_string)s", "minute_of_hour_decimal_string"),
    (u"ss", "(?P<second_of_minute>\d\d)",
     "%(second_of_minute)02d", "second_of_minute"),
    (u",tt", ",(?P<second_of_minute_decimal>\d+)",
     ",%(second_of_minute_decimal_string)s",
     "second_of_minute_decimal_string"),
    (u"\.tt", "\.(?P<second_of_minute_decimal>\d+)",
     ".%(second_of_minute_decimal_string)s",
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

LOCALE_TIMEZONE_BASIC = timezone.get_timezone_format_for_locale()
LOCALE_TIMEZONE_BASIC_NO_Z = LOCALE_TIMEZONE_BASIC
if LOCALE_TIMEZONE_BASIC_NO_Z == "Z":
    LOCALE_TIMEZONE_BASIC_NO_Z = "+0000"
LOCALE_TIMEZONE_EXTENDED = timezone.get_timezone_format_for_locale(
    extended_mode=True)
LOCALE_TIMEZONE_EXTENDED_NO_Z = LOCALE_TIMEZONE_EXTENDED
if LOCALE_TIMEZONE_EXTENDED_NO_Z == "Z":
    LOCALE_TIMEZONE_EXTENDED_NO_Z = "+0000"
    
# Note: we only accept the following subset of strftime syntax.
# This is due to inconsistencies with the ISO 8601 representations.
REC_SPLIT_STRFTIME_DIRECTIVE = re.compile(r"(%\w)")
REC_STRFTIME_DIRECTIVE_TOKEN = re.compile(r"^%\w$")
STRFTIME_TRANSLATE_INFO = {
    "%d": ["day_of_month"],
    "%F": ["century", "year_of_century", "-", "month_of_year", "-",
           "day_of_month"],
    "%H": ["hour_of_day"],
    "%j": ["day_of_year"],
    "%m": ["month_of_year"],
    "%M": ["minute_of_hour"],
    "%s": (
        "(?P<seconds_since_unix_epoch>\d+[,.]?\d*)",
        "%(seconds_since_unix_epoch)s", "seconds_since_unix_epoch"),
    "%S": ["second_of_minute"],
    "%X": ["hour_of_day", ":", "minute_of_hour", ":", "second_of_minute"],
    "%Y": ["century", "year_of_century"],
    "%z": LOCALE_TIMEZONE_BASIC_NO_Z,
}
STRPTIME_EXCLUSIVE_GROUP_INFO = {
    "%X": ("%H", "%M", "%S"),
    "%F": ("%Y", "%y", "%m", "%d"),
    "%s": tuple([i for i in STRFTIME_TRANSLATE_INFO if i != "%s"])
}


class StrftimeSyntaxError(ValueError):

    """An error denoting invalid or unsupported strftime/strptime syntax."""

    BAD_STRFTIME_INPUT = "Invalid strftime/strptime representation: {0}"

    def __str__(self):
        return self.BAD_STRFTIME_INPUT.format(*self.args)


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


def translate_strftime_token(strftime_token, num_expanded_year_digits=2):
    """Convert a strftime format into our own dump format."""
    return _translate_strftime_token(
        strftime_token, dump_mode=True,
        num_expanded_year_digits=num_expanded_year_digits
    )


def translate_strptime_token(strptime_token, num_expanded_year_digits=2):
    """Convert a strptime format into our own parsing format."""
    return _translate_strftime_token(
        strptime_token, dump_mode=False,
        num_expanded_year_digits=num_expanded_year_digits
    )


def _translate_strftime_token(strftime_token, dump_mode=False,
                              num_expanded_year_digits=2):
    if strftime_token not in STRFTIME_TRANSLATE_INFO:
        raise StrftimeSyntaxError(strftime_token)
    our_translation = ""
    our_translate_info = (
        get_date_translate_info(
            num_expanded_year_digits=num_expanded_year_digits) +
        get_time_translate_info() +
        get_timezone_translate_info()
    )
    attr_names = STRFTIME_TRANSLATE_INFO[strftime_token]
    if isinstance(attr_names, basestring):
        if dump_mode:
            return attr_names, []
        return re.escape(attr_names), []
    if isinstance(attr_names, tuple):
        (substitute, format_, name) = attr_names
        if dump_mode:
            our_translation += format_
        else:
            our_translation += substitute
        return our_translation, [name]
    attr_names = list(attr_names)
    for attr_name in list(attr_names):
        for expr_regex, substitute, format_, name in our_translate_info:
            if name == attr_name:
                if dump_mode:
                    our_translation += format_
                else:
                    our_translation += substitute
                break
        else:
            # Not an attribute name, just a delimiter or something.
            our_translation += attr_name
            attr_names.remove(attr_name)
    return our_translation, attr_names
