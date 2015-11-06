import re

from parsec.validate import validator as vdr
from parsec.validate import (
    coercers, _strip_and_unquote, _strip_and_unquote_list, _expand_list,
    IllegalValueError
)
from parsec.util import itemstr
from parsec.upgrade import upgrader, converter
from parsec.fileparse import parse
from parsec.config import config
from cylc.syntax_flags import (
    set_syntax_version, VERSION_PREV, VERSION_NEW, SyntaxVersionError
)
from isodatetime.dumpers import TimePointDumper
from isodatetime.data import Calendar, TimePoint
from isodatetime.parsers import TimePointParser, DurationParser
from cylc.cycling.integer import REC_INTERVAL as REC_INTEGER_INTERVAL

interval_parser = DurationParser()


def coerce_interval(value, keys, args, back_comp_unit_factor=1,
                    check_syntax_version=True):
    """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
    value = _strip_and_unquote(keys, value)
    try:
        backwards_compat_value = float(value) * back_comp_unit_factor
    except (TypeError, ValueError):
        pass
    else:
        if check_syntax_version:
            set_syntax_version(VERSION_PREV,
                               "integer interval: %s" % itemstr(
                                   keys[:-1], keys[-1], value))
        return backwards_compat_value
    try:
        interval = interval_parser.parse(value)
    except ValueError:
        raise IllegalValueError("ISO 8601 interval", keys, value)
    if check_syntax_version:
        try:
            set_syntax_version(VERSION_NEW,
                               "ISO 8601 interval: %s" % itemstr(
                                   keys[:-1], keys[-1], value))
        except SyntaxVersionError as exc:
            raise Exception(str(exc))
    days, seconds = interval.get_days_and_seconds()
    seconds += days * Calendar.default().SECONDS_IN_DAY
    return seconds


def coerce_interval_list(value, keys, args, back_comp_unit_factor=1,
                         check_syntax_version=True):
    """Coerce a list of intervals (or numbers: back-comp) into seconds."""
    values_list = _strip_and_unquote_list(keys, value)
    type_converter = (
        lambda v: coerce_interval(
            v, keys, args,
            back_comp_unit_factor=back_comp_unit_factor,
            check_syntax_version=check_syntax_version,
        )
    )
    seconds_list = _expand_list(values_list, keys, type_converter, True)
    return seconds_list
