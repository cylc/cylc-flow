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

"""This provides data model dumping functionality."""

import copy
import re

from . import parser_spec
from . import util


class TimePointDumper(object):

    """Dump TimePoint instances to strings using particular formats.

    A format can be specified in the self.dump method via the
    formatting_string argument. Unlike Python's datetime strftime
    method, this uses normal/Unicode character patterns to represent
    which pieces of information to output where. A full reference
    of valid patterns is found in the parser_spec module, with lots
    of examples (coincidentally, used to generate the parsing).
    Anything not matched will get left as it is in the string.
    Specifying a particular timezone will result in a timezone
    conversion of the date/time information before it is output.

    For example, the following formatting_string
    'CCYYMMDDThhmmZ' is made up of:
    CC - year (century) information, e.g. 19
    YY - year (decade, year of decade) information, e.g. 85
    MM - month of year information, e.g. 05
    DD - day of month information, e.g. 31
    T - left alone, date/time separator
    hh - hour of day information, e.g. 06
    mm - minute of hour information, e.g. 58
    Z - Zulu or UTC zero-offset timezone, left in, forces timezone
    conversion
    and might dump a TimePoint instance like this: '19850531T0658Z'.

    Keyword arguments:
    num_expanded_year_digits - an integer (default 2) that indicates
    how many extra year digits to apply if appropriate (and if the
    user requests that information).

    """

    def __init__(self, num_expanded_year_digits=2):
        self._rec_formats = {"date": [], "time": [], "timezone": []}
        self._time_designator = parser_spec.TIME_DESIGNATOR
        for info, key in [
                (parser_spec.get_date_translate_info(
                    num_expanded_year_digits),
                 "date"),
                (parser_spec.get_time_translate_info(), "time"),
                (parser_spec.get_timezone_translate_info(), "timezone")]:
            for regex, regex_sub, format_sub, prop_name in info:
                rec = re.compile(regex)
                self._rec_formats[key].append((rec, format_sub, prop_name))

    def dump(self, timepoint, formatting_string):
        """Dump a timepoint according to formatting_string.

        The syntax for formatting_string is the syntax used for the
        TimePointParser internals. See TimePointParser.*_TRANSLATE_INFO.

        """
        expression, properties = self._get_expression_and_properties(
            formatting_string)
        if (not timepoint.truncated and
                ("week_of_year" in properties or
                 "day_of_week" in properties) and
                 not ("month_of_year" in properties or
                      "day_of_month" in properties or
                      "day_of_year" in properties)):
            # We need the year to be in week years.
            timepoint = copy.copy(timepoint).to_week_date()
        if "Z" in expression and (
                timepoint.time_zone.hours or timepoint.time_zone.minutes):
            timepoint = copy.copy(timepoint)
            timepoint.set_time_zone_to_utc()   
        property_map = {}
        for property_ in properties:
            property_map[property_] = timepoint.get(property_)
        return expression % property_map

    @util.cache_results
    def _get_expression_and_properties(self, formatting_string):
        date_time_strings = formatting_string.split(
            self._time_designator)
        date_string = date_time_strings[0]
        time_string = ""
        timezone_string = ""
        if len(date_time_strings) > 1:
            time_string = date_time_strings[1]
            if time_string.endswith("Z"):
                time_string = time_string[:-1]
                timezone_string = "Z"
            elif u"±" in time_string:
                time_string, timezone_string = time_string.split(u"±")
                timezone_string = u"±" + timezone_string
        point_prop_list = []
        string_map = {"date": "", "time": "", "timezone": ""}
        for string, key in [(date_string, "date"),
                            (time_string, "time"),
                            (timezone_string, "timezone")]:
            for rec, format_sub, prop in self._rec_formats[key]:
                new_string = rec.sub(format_sub, string)
                if new_string != string and prop is not None:
                    point_prop_list.append(prop)
                string = new_string
            string_map[key] = string
        expression = string_map["date"]
        if string_map["time"]:
            expression += self._time_designator + string_map["time"]
        expression += string_map["timezone"]
        return expression, tuple(point_prop_list)
