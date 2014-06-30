#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re

from parsec.validate import validator as vdr
from parsec.validate import (
    coercers, _strip_and_unquote, _strip_and_unquote_list, _expand_list,
    IllegalValueError
)
from parsec.upgrade import upgrader, converter
from parsec.fileparse import parse
from parsec.config import config
from isodatetime.dumpers import TimePointDumper
from isodatetime.data import TimePoint, SECONDS_IN_DAY
from isodatetime.parsers import TimePointParser, TimeIntervalParser


"Define all legal items and values for cylc suite definition files."

interval_parser = TimeIntervalParser()


def _coerce_cycletime( value, keys, args ):
    """Coerce value to a cycle time."""
    value = _strip_and_unquote( keys, value )
    if re.match(r"\d+$", value):
        # Old cycle time format, or integer format.
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
        raise IllegalValueError("cycle time", keys, value)
    parser = TimePointParser()
    try:
        parser.parse(value)
    except ValueError:
        raise IllegalValueError("cycle time", keys, value)
    return value


def _coerce_cycletime_format( value, keys, args ):
    """Coerce value to a cycle time format (either CCYYMM... or %Y%m...)."""
    value = _strip_and_unquote( keys, value )
    test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                               hour_of_day=4, minute_of_hour=30,
                               second_of_minute=54)
    if "/" in value or ":" in value:
        raise IllegalValueError("cycle time format", keys, value)
    if "%" in value:
        try:
            TimePointDumper().strftime(test_timepoint, value)
        except ValueError:
            raise IllegalValueError("cycle time format", keys, value)
        return value
    if "X" in value:
        for i in range(1, 101):
            dumper = TimePointDumper(num_expanded_year_digits=i)
            try:
                dumper.dump(test_timepoint, value)
            except ValueError:
                continue
            return value
        raise IllegalValueError("cycle time format", keys, value)
    dumper = TimePointDumper()
    try:
        dumper.dump(test_timepoint, value)
    except ValueError:
        raise IllegalValueError("cycle time format", keys, value)
    return value


def _coerce_cycletime_time_zone( value, keys, args ):
    """Coerce value to a cycle time time zone format - Z, +13, -0800..."""
    value = _strip_and_unquote( keys, value )
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
        raise IllegalValueError("cycle time time zone format", keys, value)
    return value


def _coerce_interval( value, keys, args, back_comp_unit_factor=1 ):
    """Coerce an ISO 8601 interval (or number: back-comp) into seconds."""
    value = _strip_and_unquote( keys, value )
    try:
        return float(value) * back_comp_unit_factor
    except (TypeError, ValueError):
        pass
    try:
        interval = interval_parser.parse(value)
    except ValueError:
        raise IllegalValueError("ISO 8601 interval", keys, value)
    days, seconds = interval.get_days_and_seconds()
    seconds += days * SECONDS_IN_DAY
    return seconds


def _coerce_interval_list( value, keys, args, back_comp_unit_factor=1 ):
    """Coerce a list of intervals (or numbers: back-comp) into seconds."""
    values_list = _strip_and_unquote_list( keys, value )
    type_converter = (
        lambda v: _coerce_interval(
            v, keys, args,
            back_comp_unit_factor=back_comp_unit_factor
        )
    )
    seconds_list = _expand_list( values_list, keys, type_converter, True )
    return seconds_list


coercers['cycletime'] = _coerce_cycletime
coercers['cycletime_format'] = _coerce_cycletime_format
coercers['cycletime_time_zone'] = _coerce_cycletime_time_zone
coercers['interval'] = _coerce_interval
coercers['interval_minutes'] = lambda *a: _coerce_interval(
    *a, back_comp_unit_factor=60)
coercers['interval_seconds'] = _coerce_interval
coercers['interval_list'] = _coerce_interval_list
coercers['interval_minutes_list'] = lambda *a: _coerce_interval_list(
    *a, back_comp_unit_factor=60)
coercers['interval_seconds_list'] = _coerce_interval_list

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
        'job submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='interval_seconds', vmin=0, default=0 ),
            },
        'event handler submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='interval_seconds', vmin=0, default=0  ),
            },
        'poll and kill command submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='integer', vmin=0, default=0  ),
            },
        'lockserver' : {
            'enable'                          : vdr( vtype='boolean', default=False ),
            'simultaneous instances'          : vdr( vtype='boolean', default=False ),
            },
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
        'initial cycle time'                  : vdr(vtype='cycletime'),
        'final cycle time'                    : vdr(vtype='cycletime'),
        'cycling'                             : vdr(vtype='string', default="iso8601", options=["iso8601","integer"] ),
        'runahead factor'                     : vdr(vtype='integer', default=2 ),
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
                'daemon'                      : vdr( vtype='string'),
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
            'work sub-directory'              : vdr( vtype='string', default='$CYLC_TASK_ID' ),
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
        'initial cycle time'                  : vdr( vtype='cycletime' ),
        'final cycle time'                    : vdr( vtype='cycletime' ),
        'collapsed families'                  : vdr( vtype='string_list', default=[] ),
        'use node color for edges'            : vdr( vtype='boolean', default=True ),
        'use node color for labels'           : vdr( vtype='boolean', default=False ),
        'default node attributes'             : vdr( vtype='string_list', default=['style=unfilled', 'color=black', 'shape=box']),
        'default edge attributes'             : vdr( vtype='string_list', default=['color=black']),
        'enable live graph movie'             : vdr( vtype='boolean', default=False ),
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
    # TODO - replace ISO version here:
    u.obsolete( '5.4.ISO', ['visualization', 'runtime graph'] )
    u.obsolete( '5.4.ISO', ['development'] )
    u.deprecate( '5.4.ISO', ['scheduling', 'runahead limit'], ['scheduling', 'runahead factor'],
            converter( lambda x:'2', 'using default runahead factor' ))
    u.upgrade()

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
