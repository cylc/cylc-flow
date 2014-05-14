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

"""This provides ISO 8601 parsing functionality."""

import re
import sre_constants

from . import data
from . import dumpers
from . import parser_spec
from . import timezone


class ISO8601SyntaxError(ValueError):

    """An error denoting invalid input syntax."""

    BAD_TIME_INPUT = "Invalid ISO 8601 {0} representation: {1}"

    def __str__(self):
        return self.BAD_TIME_INPUT.format(*self.args)


class StrptimeConversionError(ValueError):

    """An error denoting bad conversion from a strftime/strptime format."""

    BAD_CONVERSION = "Bad conversion for strftime/strptime input {0}: {1}."""

    def __str__(self):
        return self.BAD_CONVERSION.format(*self.args)


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
            return data.TimeRecurrence(
                repetitions=repetitions,
                start_point=start_point,
                end_point=end_point,
                interval=interval
            )
        raise ISO8601SyntaxError("recurrence", expression)

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

    assumed_time_zone (default None) is a tuple of hours (integer)
    and minutes (integer) that specifies that dates and times
    without time zone information should be set to have a time zone
    whose offset from UTC is the (hours, minutes) information in this
    variable. To assume UTC, set this to (0, 0).

    default_to_unknown_time_zone (default False) specifies that
    dates and times without time zone information (in the absence of
    assumed_time_zone) should be left with an unknown time zone
    setting. Otherwise, the current local time zone will be used.

    dump_format (default None) specifies a default custom dump format
    string for TimePoint instances. See data.TimePoint documentation
    for syntax.

    """

    def __init__(self, num_expanded_year_digits=2,
                 allow_truncated=False,
                 allow_only_basic=False,
                 assumed_time_zone=None,
                 default_to_unknown_time_zone=False,
                 dump_format=None):
        self.expanded_year_digits = num_expanded_year_digits
        self.allow_truncated = allow_truncated
        self.allow_only_basic = allow_only_basic
        self.assumed_time_zone = assumed_time_zone
        self.default_to_unknown_time_zone = default_to_unknown_time_zone
        self.dump_format = dump_format
        self._generate_regexes()

    def _generate_regexes(self):
        """Generate combined date time strings."""
        date_map = parser_spec.DATE_EXPRESSIONS
        time_map = parser_spec.TIME_EXPRESSIONS
        time_zone_map = parser_spec.TIME_ZONE_EXPRESSIONS
        self._date_regex_map = {}
        self._time_regex_map = {}
        self._time_zone_regex_map = {}
        format_ok_keys = ["basic", "extended"]
        if self.allow_only_basic:
            format_ok_keys = ["basic"]
        for format_type in format_ok_keys:
            self._date_regex_map.setdefault(format_type, {})
            self._time_regex_map.setdefault(format_type, {})
            self._time_zone_regex_map.setdefault(format_type, [])
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
            for time_zone_expr in self.get_expressions(
                    time_zone_map[format_type]):
                time_zone_regex = self.parse_time_zone_expression_to_regex(
                    time_zone_expr)
                self._time_zone_regex_map[format_type].append(
                    [re.compile(time_zone_regex), time_zone_expr])

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
        for expr_regex, substitute, format_, name in (
                parser_spec.get_date_translate_info(
                    self.expanded_year_digits)):
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse_time_expression_to_regex(self, expression):
        """Construct regular expressions for the time."""
        for expr_regex, substitute, format_, name in (
                parser_spec.get_time_translate_info()):
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse_time_zone_expression_to_regex(self, expression):
        """Construct regular expressions for the time zone."""
        for expr_regex, substitute, format_, name in (
                parser_spec.get_time_zone_translate_info(
                    )):
            expression = re.sub(expr_regex, substitute, expression)
        expression = "^" + expression + "$"
        return expression

    def parse(self, timepoint_string, dump_format=None, dump_as_parsed=False):
        """Parse a user-supplied timepoint string."""
        date_info, time_info, parsed_expr = self.get_info(timepoint_string)
        if dump_as_parsed:
            dump_format = parsed_expr
        return self._create_timepoint_from_info(
            date_info, time_info, dump_format=dump_format,
            truncated_dump_format=dump_format)

    def _create_timepoint_from_info(self, date_info, time_info,
                                    dump_format=None,
                                    truncated_dump_format=None):
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
        is_year_present = True
        if date_info.get("truncated"):
            is_year_present = False
            for property_ in ["year", "year_of_decade", "century",
                              "year_of_century", "expanded_year",
                              "year_sign"]:
                if date_info.get(property_) is not None:
                    is_year_present = True
        if is_year_present:
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
            except (IOError, TypeError, ValueError):
                pass
            if key == "time_zone_utc" and value == "Z":
                time_info.pop(key)
                time_info.update({"time_zone_hour": 0,
                                  "time_zone_minute": 0})
                continue
            time_info[key] = value
        info.update(time_info)
        if info.pop("truncated", False):
            info["truncated"] = True
        if truncated_property is not None:
            info["truncated_property"] = truncated_property
        if dump_format is None and self.dump_format:
            dump_format = self.dump_format
        if dump_format is not None:
            info.update({"dump_format": dump_format})
        if truncated_dump_format is not None:
            info.update({"truncated_dump_format": truncated_dump_format})
        return data.TimePoint(**info)

    def strptime(self, strptime_data_string, strptime_format_string,
                 dump_format=None):
        """Implement equivalent of Python 2's datetime.datetime.strptime.

        Return an isodatetime.data.TimePoint representing
        strptime_data_string based on the format given in
        strptime_format_string.
        dump_format is a custom dump format string (not in strftime
        format).

        """
        split_format = parser_spec.REC_SPLIT_STRFTIME_DIRECTIVE.split(
            strptime_format_string)
        regex = "^"
        for item in split_format:
            if parser_spec.REC_STRFTIME_DIRECTIVE_TOKEN.search(item):
                item_regex, item_properties = (
                    parser_spec.translate_strptime_token(item))
                regex += item_regex
            else:
                regex += re.escape(item)
        regex += "$"
        return self._parse_from_custom_regex(regex, strptime_data_string,
            dump_format=None, source=strptime_format_string)

    def _parse_from_custom_regex(self, regex, data_string, dump_format=None,
                                 source=None):
        """Parse data_string according to the regular expression in regex."""
        try:
            compiled_regex = re.compile(regex)
        except sre_constants.error:
            raise StrptimeConversionError(source, regex)
        result = compiled_regex.match(data_string)
        if not result:
            raise StrptimeConversionError(source, data_string)
        info = result.groupdict()
        for property_, value in info.items():
            if property_ in data.PARSE_PROPERTY_TRANSLATORS:
                info.pop(property_)
                translator = data.PARSE_PROPERTY_TRANSLATORS[property_]
                info.update(translator(value))
        date_info_keys = []
        for expr_regex, substitute, format_, name in (
                parser_spec.get_date_translate_info(
                    self.expanded_year_digits)):
            date_info_keys.append(name)
        time_info_keys = []
        for expr_regex, substitute, format_, name in (
                parser_spec.get_time_translate_info()):
            time_info_keys.append(name)
        date_info = {}
        time_info = {}
        time_zone_info = {}
        for key, value in info.items():
            if key in date_info_keys:
                date_info[key] = value
            elif key in time_info_keys:
                time_info[key] = value
            else:
                time_zone_info[key] = value
        time_zone_info = self.process_time_zone_info(time_zone_info)
        time_info.update(time_zone_info)
        return self._create_timepoint_from_info(
            date_info, time_info, dump_format=dump_format)

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
                        return ((format_key, type_key, expr),
                                result.groupdict())
        raise ISO8601SyntaxError("date", date_string)

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
                        return expr, result.groupdict()
        raise ISO8601SyntaxError("time", time_string)

    def get_time_zone_info(self, time_zone_string, bad_formats=None):
        """Return the properties from a time zone string."""
        if bad_formats is None:
            bad_formats = []
        for format_key, regex_list in self._time_zone_regex_map.items():
            if format_key in bad_formats:
                continue
            for regex, expr in regex_list:
                result = regex.match(time_zone_string)
                if result:
                    return expr, result.groupdict()
        raise ISO8601SyntaxError("time zone", time_zone_string)

    def get_info(self, timepoint_string):
        """Return the date and time properties from a timepoint string."""
        date_time_time_zone = timepoint_string.split(
            parser_spec.TIME_DESIGNATOR)
        parsed_expr = ""
        if len(date_time_time_zone) == 1:
            date = date_time_time_zone[0]
            keys, date_info = self.get_date_info(date)
            format_key, type_key, date_expr = keys
            parsed_expr += date_expr
            time_info = {}
            time_zone_info = (
                self.process_time_zone_info({}))
            time_info.update(time_zone_info)
        else:
            date, time_time_zone = date_time_time_zone
            if not date and self.allow_truncated:
                keys = (None, "truncated", "")
                date_info = {"truncated": True}
            else:
                keys, date_info = self.get_date_info(date,
                                                     bad_types=["reduced"])
            format_key, type_key, date_expr = keys
            parsed_expr += date_expr
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
            if time_time_zone.endswith("Z"):
                time, time_zone = time_time_zone[:-1], "Z"
            elif "+" in time_time_zone:
                time, time_zone = time_time_zone.split("+")
                time_zone = "+" + time_zone
            elif "-" in time_time_zone:
                time, time_zone = time_time_zone.rsplit("-", 1)
                time_zone = "-" + time_zone
                # Make sure this isn't just a truncated time.
                try:
                    time_expr, time_info = self.get_time_info(
                        time,
                        bad_formats=bad_formats,
                        bad_types=bad_types
                    )
                    time_zone_expr, time_zone_info = self.get_time_zone_info(
                        time_zone,
                        bad_formats=bad_formats
                    )
                except ISO8601SyntaxError:
                    time = time_time_zone
                    time_zone = None
            else:
                time = time_time_zone
                time_zone = None
            if time_zone is None:
                time_zone_info = {}
                time_zone_expr = ""
                time_zone_info = (
                    self.process_time_zone_info(time_zone_info))
            else:
                time_zone_expr, time_zone_info = self.get_time_zone_info(
                    time_zone,
                    bad_formats=bad_formats
                )
                time_zone_info = self.process_time_zone_info(time_zone_info)
            time_expr, time_info = self.get_time_info(
                                           time, bad_formats=bad_formats,
                                           bad_types=bad_types)
            parsed_expr += parser_spec.TIME_DESIGNATOR + (
                time_expr + time_zone_expr)
            time_info.update(time_zone_info)
        return date_info, time_info, parsed_expr

    def process_time_zone_info(self, time_zone_info=None):
        """Rationalise time zone data and set defaults if appropriate."""
        if time_zone_info is None:
            time_zone_info = {}
        if not time_zone_info:
            # There is no time zone information specified.
            if self.assumed_time_zone is None:
                # No given value to assume.
                if self.default_to_unknown_time_zone:
                    # Return no time zone information.
                    return {} 
                # Set the time zone to the current local time zone.
                utc_hour_offset, utc_minute_offset = (
                    timezone.get_local_time_zone())
                time_zone_info["time_zone_hour"] = utc_hour_offset
                time_zone_info["time_zone_minute"] = utc_minute_offset
                return time_zone_info
            else:
                # Set the time zone to a given value.
                utc_hour_offset, utc_minute_offset = self.assumed_time_zone
                time_zone_info["time_zone_hour"] = utc_hour_offset
                time_zone_info["time_zone_minute"] = utc_minute_offset
                return time_zone_info
        if time_zone_info.pop("time_zone_sign", "+") == "-":
            time_zone_info["time_zone_hour"] = (
                -int(time_zone_info["time_zone_hour"]))
            if "time_zone_minute" in time_zone_info:
                time_zone_info["time_zone_minute"] = (
                    -int(time_zone_info["time_zone_minute"]))
        return time_zone_info


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
        re.compile(r"""^P(?P<weeks>\d+)W$""", re.X)
    ]

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
            return data.TimeInterval(**result_map)
        if expression.startswith("P"):
            try:
                timepoint = parse_timepoint_expression(
                    expression[1:], allow_truncated=False,
                    assumed_time_zone=(0, 0)
                )
            except ISO8601SyntaxError:
                raise
            if timepoint.get_is_week_date():
                raise ISO8601SyntaxError("duration", expression)
            result_map = {}
            result_map["years"] = timepoint.year
            if timepoint.get_is_calendar_date():
                result_map["months"] = timepoint.month_of_year
                result_map["days"] = timepoint.day_of_month
            if timepoint.get_is_ordinal_date():
                result_map["days"] = timepoint.day_of_year
            result_map["hours"] = timepoint.hour_of_day
            if timepoint.minute_of_hour is not None:
                result_map["minutes"] = timepoint.minute_of_hour
            if timepoint.second_of_minute is not None:
                result_map["seconds"] = timepoint.second_of_minute
            return data.TimeInterval(**result_map)
        raise ISO8601SyntaxError("duration", expression)


def parse_timepoint_expression(timepoint_expression, **kwargs):
    """Return a data model that represents timepoint_expression."""
    parser = TimePointParser(**kwargs)
    return parser.parse(timepoint_expression)
