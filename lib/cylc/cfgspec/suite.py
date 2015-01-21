#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

"Define all legal items and values for cylc suite definition files."

interval_parser = DurationParser()

def _coerce_cycleinterval( value, keys, args ):
    """Coerce value to a cycle interval."""
    value = _strip_and_unquote( keys, value )
    if value.isdigit():
        # Old runahead limit format.
        set_syntax_version(VERSION_PREV,
                           "integer interval for %s" % itemstr(
                               keys[:-1], keys[-1], value))
        return value
    if REC_INTEGER_INTERVAL.match(value):
        # New integer cycling format.
        set_syntax_version(VERSION_NEW,
                           "integer interval for %s" % itemstr(
                               keys[:-1], keys[-1], value))
        return value
    parser = DurationParser()
    try:
        parser.parse(value)
    except ValueError:
        raise IllegalValueError("interval", keys, value)
    set_syntax_version(VERSION_NEW,
                       "ISO 8601 interval for %s" % itemstr(
                           keys[:-1], keys[-1], value))
    return value

def _coerce_cycletime( value, keys, args ):
    """Coerce value to a cycle point."""
    value = _strip_and_unquote( keys, value )
    if re.match(r"\d+$", value):
        # Could be an old date-time cycle point format, or integer format.
        return value
    if value.startswith("-") or value.startswith("+"):
        # We don't know the value given for num expanded year digits...
        for i in range(1, 101):
            parser = TimePointParser(num_expanded_year_digits=i)
            try:
                parser.parse(value)
            except ValueError:
                continue
            return value
        raise IllegalValueError("cycle point", keys, value)
    parser = TimePointParser()
    try:
        parser.parse(value)
    except ValueError:
        raise IllegalValueError("cycle point", keys, value)
    set_syntax_version(VERSION_NEW,
                       "cycle point: %s" % itemstr(
                           keys[:-1], keys[-1], value))
    return value


def _coerce_cycletime_format( value, keys, args ):
    """Coerce value to a cycle point format (either CCYYMM... or %Y%m...)."""
    value = _strip_and_unquote( keys, value )
    set_syntax_version(VERSION_NEW,
                       "use of [cylc]cycle point format",
                       exc_class=IllegalValueError,
                       exc_args=("cycle point format", keys, value))
    test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                               hour_of_day=4, minute_of_hour=30,
                               second_of_minute=54)
    if "/" in value or ":" in value:
        raise IllegalValueError("cycle point format", keys, value)
    if "%" in value:
        try:
            TimePointDumper().strftime(test_timepoint, value)
        except ValueError:
            raise IllegalValueError("cycle point format", keys, value)
        return value
    if "X" in value:
        for i in range(1, 101):
            dumper = TimePointDumper(num_expanded_year_digits=i)
            try:
                dumper.dump(test_timepoint, value)
            except ValueError:
                continue
            return value
        raise IllegalValueError("cycle point format", keys, value)
    dumper = TimePointDumper()
    try:
        dumper.dump(test_timepoint, value)
    except ValueError:
        raise IllegalValueError("cycle point format", keys, value)
    return value


def _coerce_cycletime_time_zone( value, keys, args ):
    """Coerce value to a cycle point time zone format - Z, +13, -0800..."""
    value = _strip_and_unquote( keys, value )
    set_syntax_version(VERSION_NEW,
                       "use of [cylc]cycle point time zone format",
                       exc_class=IllegalValueError,
                       exc_args=("cycle point time zone format", keys, value))
    test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                               hour_of_day=4, minute_of_hour=30,
                               second_of_minute=54)
    dumper = TimePointDumper()
    test_timepoint_string = dumper.dump(test_timepoint, "CCYYMMDDThhmmss")
    test_timepoint_string += value
    parser = TimePointParser(allow_only_basic=True)
    try:
        parser.parse(test_timepoint_string)
    except ValueError:
        raise IllegalValueError("cycle point time zone format", keys, value)
    return value


def _coerce_final_cycletime( value, keys, args ):
    """Coerce final cycle point."""
    value = _strip_and_unquote( keys, value )
    return value


def coerce_interval( value, keys, args, back_comp_unit_factor=1 ):
    """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
    value = _strip_and_unquote( keys, value )
    try:
        backwards_compat_value = float(value) * back_comp_unit_factor
    except (TypeError, ValueError):
        pass
    else:
        set_syntax_version(VERSION_PREV,
                           "integer interval: %s" % itemstr(
                               keys[:-1], keys[-1], value))
        return backwards_compat_value
    try:
        interval = interval_parser.parse(value)
    except ValueError:
        raise IllegalValueError("ISO 8601 interval", keys, value)
    try:
        set_syntax_version(VERSION_NEW,
                           "ISO 8601 interval: %s" % itemstr(
                               keys[:-1], keys[-1], value))
    except SyntaxVersionError as exc:
        raise Exception(str(exc))
    days, seconds = interval.get_days_and_seconds()
    seconds += days * Calendar.default().SECONDS_IN_DAY
    return seconds


def coerce_interval_list( value, keys, args, back_comp_unit_factor=1 ):
    """Coerce a list of intervals (or numbers: back-comp) into seconds."""
    values_list = _strip_and_unquote_list( keys, value )
    type_converter = (
        lambda v: coerce_interval(
            v, keys, args,
            back_comp_unit_factor=back_comp_unit_factor
        )
    )
    seconds_list = _expand_list( values_list, keys, type_converter, True )
    return seconds_list


coercers['cycletime'] = _coerce_cycletime
coercers['cycletime_format'] = _coerce_cycletime_format
coercers['cycletime_time_zone'] = _coerce_cycletime_time_zone
coercers['cycleinterval'] = _coerce_cycleinterval
coercers['final_cycletime'] = _coerce_final_cycletime
coercers['interval'] = coerce_interval
coercers['interval_minutes'] = lambda *a: coerce_interval(
    *a, back_comp_unit_factor=60)
coercers['interval_seconds'] = coerce_interval
coercers['interval_list'] = coerce_interval_list
coercers['interval_minutes_list'] = lambda *a: coerce_interval_list(
    *a, back_comp_unit_factor=60)
coercers['interval_seconds_list'] = coerce_interval_list


SPEC = {
    'title'                                   : vdr( vtype='string', default="" ),
    'description'                             : vdr( vtype='string', default="" ),
    'cylc' : {
        'UTC mode'                            : vdr( vtype='boolean', default=False),
        'cycle point format'                  : vdr( vtype='cycletime_format', default=None),
        'cycle point num expanded year digits': vdr( vtype='integer', default=0),
        'cycle point time zone'               : vdr( vtype='cycletime_time_zone', default=None),
        'required run mode'                   : vdr( vtype='string', options=['live','dummy','simulation'] ),
        'force run mode'                      : vdr( vtype='string', options=['live','dummy','simulation'] ),
        'abort if any task fails'             : vdr( vtype='boolean', default=False ),
        'log resolved dependencies'           : vdr( vtype='boolean', default=False ),
        'environment' : {
            '__MANY__'                        : vdr( vtype='string' ),
            },
        'event hooks' : {
            'startup handler'                 : vdr( vtype='string_list', default=[] ),
            'timeout handler'                 : vdr( vtype='string_list', default=[] ),
            'shutdown handler'                : vdr( vtype='string_list', default=[] ),
            'timeout'                         : vdr( vtype='interval_minutes'  ),
            'reset timer'                     : vdr( vtype='boolean', default=True ),
            'abort if startup handler fails'  : vdr( vtype='boolean', default=False ),
            'abort if shutdown handler fails' : vdr( vtype='boolean', default=False ),
            'abort if timeout handler fails'  : vdr( vtype='boolean', default=False ),
            'abort on timeout'                : vdr( vtype='boolean', default=False ),
            },
        'simulation mode' : {
            'disable suite event hooks'       : vdr( vtype='boolean', default=True ),
            },
        'dummy mode' : {
            'disable suite event hooks'       : vdr( vtype='boolean', default=True ),
            },
        'reference test' : {
            'suite shutdown event handler'    : vdr( vtype='string', default='cylc hook check-triggering' ),
            'required run mode'               : vdr( vtype='string', options=[ 'live','simulation','dummy'] ),
            'allow task failures'             : vdr( vtype='boolean', default=False ),
            'expected task failures'          : vdr( vtype='string_list', default=[] ),
            'live mode suite timeout'         : vdr( vtype='interval_minutes', default=60 ),
            'dummy mode suite timeout'        : vdr( vtype='interval_minutes', default=60 ),
            'simulation mode suite timeout'   : vdr( vtype='interval_minutes', default=60 ),
            },
        },
    'scheduling' : {
        'initial cycle point'                 : vdr(vtype='cycletime'),
        'final cycle point'                   : vdr(vtype='final_cycletime'),
        'cycling mode'                        : vdr(vtype='string', default=Calendar.MODE_GREGORIAN, options=Calendar.MODES.keys() + ["integer"] ),
        'runahead limit'                      : vdr(vtype='cycleinterval' ),
        'max active cycle points'             : vdr(vtype='integer', default=3),
        'queues' : {
            'default' : {
                'limit'                       : vdr( vtype='integer', default=0),
                },
            '__MANY__' : {
                'limit'                       : vdr(vtype='integer', default=0 ),
                'members'                     : vdr(vtype='string_list', default=[]),
                },
            },
        'special tasks' : {
            'clock-triggered'                 : vdr(vtype='string_list', default=[]),
            'sequential'                      : vdr(vtype='string_list', default=[]),
            'start-up'                        : vdr(vtype='string_list', default=[]),
            'cold-start'                      : vdr(vtype='string_list', default=[]),
            'exclude at start-up'             : vdr(vtype='string_list', default=[]),
            'include at start-up'             : vdr(vtype='string_list', default=[]),
            },
        'dependencies' : {
            'graph'                           : vdr( vtype='string'),
            '__MANY__' :
            {
                'graph'                       : vdr( vtype='string'),
                },
            },
        },
    'runtime' : {
        '__MANY__' : {
            'inherit'                         : vdr( vtype='string_list', default=[] ),
            'title'                           : vdr( vtype='string', default="" ),
            'description'                     : vdr( vtype='string', default="" ),
            'initial scripting'               : vdr( vtype='string' ),
            'environment scripting'           : vdr( vtype='string' ),
            'pre-command scripting'           : vdr( vtype='string' ),
            'command scripting'               : vdr( vtype='string', default='echo Default command scripting; sleep $(cylc rnd 1 16)'),
            'post-command scripting'          : vdr( vtype='string' ),
            'retry delays'                    : vdr( vtype='interval_minutes_list', default=[] ),
            'manual completion'               : vdr( vtype='boolean', default=False ),
            'extra log files'                 : vdr( vtype='string_list', default=[] ),
            'enable resurrection'             : vdr( vtype='boolean', default=False ),
            'work sub-directory'              : vdr( vtype='string', default='$CYLC_TASK_CYCLE_POINT/$CYLC_TASK_NAME' ),
            'submission polling intervals'    : vdr( vtype='interval_minutes_list', default=[] ),
            'execution polling intervals'     : vdr( vtype='interval_minutes_list', default=[] ),
            'environment filter' : {
                'include'                     : vdr( vtype='string_list' ),
                'exclude'                     : vdr( vtype='string_list' ),
            },
            'simulation mode' :  {
                'run time range'              : vdr( vtype='interval_seconds_list', default=[1, 16]),
                'simulate failure'            : vdr( vtype='boolean', default=False ),
                'disable task event hooks'    : vdr( vtype='boolean', default=True ),
                'disable retries'             : vdr( vtype='boolean', default=True ),
                },
            'dummy mode' : {
                'command scripting'              : vdr( vtype='string', default='echo Dummy command scripting; sleep $(cylc rnd 1 16)'),
                'disable pre-command scripting'  : vdr( vtype='boolean', default=True ),
                'disable post-command scripting' : vdr( vtype='boolean', default=True ),
                'disable task event hooks'       : vdr( vtype='boolean', default=True ),
                'disable retries'                : vdr( vtype='boolean', default=True ),
                },
            'job submission' : {
                'method'                      : vdr( vtype='string', default='background' ),
                'command template'            : vdr( vtype='string' ),
                'shell'                       : vdr( vtype='string',  default='/bin/bash' ),
                'retry delays'                : vdr( vtype='interval_minutes_list', default=[] ),
                },
            'remote' : {
                'host'                        : vdr( vtype='string' ),
                'owner'                       : vdr( vtype='string' ),
                'suite definition directory'  : vdr( vtype='string' ),
                },
            'event hooks' : {
                'submitted handler'           : vdr( vtype='string_list', default=[] ),
                'started handler'             : vdr( vtype='string_list', default=[] ),
                'succeeded handler'           : vdr( vtype='string_list', default=[] ),
                'failed handler'              : vdr( vtype='string_list', default=[] ),
                'submission failed handler'   : vdr( vtype='string_list', default=[] ),
                'warning handler'             : vdr( vtype='string_list', default=[] ),
                'retry handler'               : vdr( vtype='string_list', default=[] ),
                'submission retry handler'    : vdr( vtype='string_list', default=[] ),
                'submission timeout handler'  : vdr( vtype='string_list', default=[] ),
                'submission timeout'          : vdr( vtype='interval_minutes' ),
                'execution timeout handler'   : vdr( vtype='string_list', default=[] ),
                'execution timeout'           : vdr( vtype='interval_minutes'),
                'reset timer'                 : vdr( vtype='boolean', default=False ),
                },
            'suite state polling' : {
                'user'                        : vdr( vtype='string' ),
                'host'                        : vdr( vtype='string' ),
                'interval'                    : vdr( vtype='interval_seconds' ),
                'max-polls'                   : vdr( vtype='integer' ),
                'run-dir'                     : vdr( vtype='string' ),
                'verbose mode'                : vdr( vtype='boolean' ),
                },
            'environment' : {
                '__MANY__'                    : vdr( vtype='string' ),
                },
            'directives' : {
                '__MANY__'                    : vdr( vtype='string' ),
                },
            'outputs' : {
                '__MANY__'                    : vdr( vtype='string' ),
                },
            },
        },
    'visualization' : {
        'initial cycle point'                 : vdr( vtype='cycletime' ),
        'final cycle point'                   : vdr( vtype='final_cycletime' ),
        'number of cycle points'              : vdr( vtype='integer', default=3 ),
        'collapsed families'                  : vdr( vtype='string_list', default=[] ),
        'use node color for edges'            : vdr( vtype='boolean', default=True ),
        'use node color for labels'           : vdr( vtype='boolean', default=False ),
        'default node attributes'             : vdr( vtype='string_list', default=['style=unfilled', 'color=black', 'shape=box']),
        'default edge attributes'             : vdr( vtype='string_list', default=['color=black']),
        'node groups' : {
            '__MANY__'                        : vdr( vtype='string_list', default=[] ),
            },
        'node attributes' : {
            '__MANY__'                        : vdr( vtype='string_list', default=[] ),
            },
        },
    }

def upg( cfg, descr ):
    u = upgrader( cfg, descr )
    u.deprecate( '5.2.0', ['cylc','event handler execution'], ['cylc','event handler submission'] )
    # TODO - should abort if obsoleted items are encountered
    u.obsolete( '5.4.7', ['scheduling','special tasks','explicit restart outputs'] )
    u.obsolete( '5.4.11', ['cylc', 'accelerated clock'] )
    u.obsolete( '6.0.0', ['visualization', 'runtime graph'] )
    u.obsolete('6.1.3', ['visualization', 'enable live graph movie'])
    u.obsolete( '6.0.0', ['development'] )
    u.deprecate(
        '6.0.0',
        ['scheduling', 'initial cycle time'], ['scheduling', 'initial cycle point'],
        converter( lambda x: x, 'changed naming to reflect non-date-time cycling' )
    )
    u.deprecate(
        '6.0.0',
        ['scheduling', 'final cycle time'], ['scheduling', 'final cycle point'],
        converter( lambda x: x, 'changed naming to reflect non-date-time cycling' )
    )
    u.deprecate(
        '6.0.0',
        ['visualization', 'initial cycle time'], ['visualization', 'initial cycle point'],
        converter( lambda x: x, 'changed naming to reflect non-date-time cycling' )
    )
    u.deprecate(
        '6.0.0',
        ['visualization', 'final cycle time'], ['visualization', 'final cycle point'],
        converter( lambda x: x, 'changed naming to reflect non-date-time cycling' )
    )
    u.obsolete('6.0.0', ['scheduling', 'dependencies', '__MANY__', 'daemon'])
    u.obsolete('6.0.0', ['cylc', 'job submission'])
    u.obsolete('6.0.0', ['cylc', 'event handler submission'])
    u.obsolete('6.0.0', ['cylc', 'poll and kill command submission'])
    u.obsolete('6.0.0', ['cylc', 'lockserver'])
    u.upgrade()

    # Force pre cylc-6 "cycling = Yearly" type suites to the explicit
    # dependency heading form for which backward compatibility is provided:
    #____________________________
    # [scheduling]
    #    cycling = Yearly
    #    [[dependencies]]
    #        [[[2014,2]]]
    #----------------------------
    # Same as (for auto upgrade):
    #----------------------------
    # [scheduling]
    #    [[dependencies]]
    #        [[[Yearly(2014,2)]]]
    #____________________________
    try:
        old_cycling_mode = cfg['scheduling']['cycling']
    except:
        pass
    else:
        if old_cycling_mode in ['Yearly', 'Monthly', 'Daily']:
            del cfg['scheduling']['cycling']
            for old_key, val in cfg['scheduling']['dependencies'].items():
                if re.match('\s*\d+,\s*\d+\s*$', old_key):
                    new_key = "%s(%s)" % (old_cycling_mode, old_key)
                    del cfg['scheduling']['dependencies'][old_key]
                    cfg['scheduling']['dependencies'][new_key] = val
        else:
            # Could be misspelled new "cycling mode" - leave it to fail.
            pass


class sconfig( config ):
    pass


suitecfg = None
cfpath = None


def get_suitecfg( fpath, force=False, tvars=[], tvars_file=None, write_proc=False ):
    global suitecfg, cfpath
    if not suitecfg or fpath != cfpath or force:
        cfpath = fpath
        # TODO - write_proc should be in loadcfg
        suitecfg = sconfig( SPEC, upg, tvars=tvars, tvars_file=tvars_file, write_proc=write_proc )
        suitecfg.loadcfg( fpath, "suite definition", strict=True )
        return suitecfg
