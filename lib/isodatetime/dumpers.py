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
    Specifying a particular time zone will result in a time zone
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
    Z - Zulu or UTC zero-offset time zone, left in, forces time zone
    conversion
    and might dump a TimePoint instance like this: '19850531T0658Z'.

    Keyword arguments:
    num_expanded_year_digits - an integer (default 2) that indicates
    how many extra year digits to apply if appropriate (and if the
    user requests that information).

    """

    def __init__(self, num_expanded_year_digits=2):
        self._rec_formats = {"date": [], "time": [], "time_zone": []}
        self._time_designator = parser_spec.TIME_DESIGNATOR
        for info, key in [
                (parser_spec.get_date_translate_info(
                    num_expanded_year_digits),
                 "date"),
                (parser_spec.get_time_translate_info(), "time"),
                (parser_spec.get_time_zone_translate_info(), "time_zone")]:
            for regex, regex_sub, format_sub, prop_name in info:
                rec = re.compile(regex)
                self._rec_formats[key].append((rec, format_sub, prop_name))

    def dump(self, timepoint, formatting_string):
        """Dump a timepoint according to formatting_string.

        The syntax for formatting_string is the syntax used for the
        TimePointParser internals. See TimePointParser.*_TRANSLATE_INFO.

        """
        if "%" in formatting_string:
            try:
                return self.strftime(timepoint, formatting_string)
            except ValueError:
                pass
        expression, properties, custom_time_zone = (
            self._get_expression_and_properties(formatting_string))
        return self._dump_expression_with_properties(
            timepoint, expression, properties,
            custom_time_zone=custom_time_zone
        )

    def strftime(self, timepoint, formatting_string):
        """Implement equivalent of Python 2's datetime.datetime.strftime.

        Dump timepoint based on the format given in formatting_string.

        """
        split_format = parser_spec.REC_SPLIT_STRFTIME_DIRECTIVE.split(
            formatting_string)
        expression = ""
        properties = []
        for item in split_format:
            if parser_spec.REC_STRFTIME_DIRECTIVE_TOKEN.search(item):
                item_expression, item_properties = (
                    parser_spec.translate_strftime_token(item))
                expression += item_expression
                properties += item_properties
            else:
                expression += item
        return self._dump_expression_with_properties(
            timepoint, expression, properties)

    def _dump_expression_with_properties(self, timepoint, expression,
                                         properties, custom_time_zone=None):
        if not timepoint.truncated:
            if ("week_of_year" in properties or
                    "day_of_week" in properties):
                if not ("month_of_year" in properties or
                            "day_of_month" in properties or
                            "day_of_year" in properties):
                    # We need the year to be in week years.
                    timepoint = timepoint.copy().to_week_date()
            elif (timepoint.get_is_week_date() and
                      ("month_of_year" in properties or
                       "day_of_month" in properties or
                       "day_of_year" in properties)):
                # We need the year to be in standard calendar years.
                timepoint = timepoint.copy().to_calendar_date()

        if custom_time_zone is not None:
            timepoint = timepoint.copy()
            if custom_time_zone == (0, 0):
                timepoint.set_time_zone_to_utc()
            else:
                current_time_zone = timepoint.get_time_zone()
                new_time_zone = current_time_zone.copy()
                new_time_zone.hours = int(custom_time_zone[0])
                new_time_zone.minutes = int(custom_time_zone[1])
                new_time_zone.unknown = False
                timepoint.set_time_zone(new_time_zone)
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
        time_zone_string = ""
        custom_time_zone = None
        if len(date_time_strings) > 1:
            time_string = date_time_strings[1]
            if time_string.endswith("Z"):
                time_string = time_string[:-1]
                time_zone_string = "Z"
                custom_time_zone = (0, 0)
            elif "+hh" in time_string:
                time_string, time_zone_string = time_string.split("+")
                time_zone_string = "+" + time_zone_string
            elif "+" in time_string:
                time_string, time_zone_string = time_string.split("+")
                time_zone_string = "+" + time_zone_string
                custom_time_zone = self.get_time_zone(time_zone_string)
            elif "-" in time_string.lstrip("-"):
                time_string, time_zone_string = time_string.split("-")
                time_zone_string = "-" + time_zone_string
                custom_time_zone = self.get_time_zone(time_zone_string)
        point_prop_list = []
        string_map = {"date": "", "time": "", "time_zone": ""}
        for string, key in [(date_string, "date"),
                            (time_string, "time"),
                            (time_zone_string, "time_zone")]:
            for rec, format_sub, prop in self._rec_formats[key]:
                new_string = rec.sub(format_sub, string)
                if new_string != string and prop is not None:
                    point_prop_list.append(prop)
                string = new_string
            string_map[key] = string
        expression = string_map["date"]
        if string_map["time"]:
            expression += self._time_designator + string_map["time"]
        expression += string_map["time_zone"]
        return expression, tuple(point_prop_list), custom_time_zone

    @util.cache_results
    def get_time_zone(self, time_zone_string):
        from . import parsers
        if not hasattr(self, "_timepoint_parser"):
            self._timepoint_parser = parsers.TimePointParser()
        try:
            (expr, info) = (
                self._timepoint_parser.get_time_zone_info(time_zone_string))
        except parsers.ISO8601SyntaxError as e:
            return None
        info = self._timepoint_parser.process_time_zone_info(info)
        if info.get('time_zone_utc'):
            return (0, 0)
        if "time_zone_hour" not in info and "time_zone_minute" not in info:
            return None
        return info.get("time_zone_hour", 0), info.get("time_zone_minute", 0)
