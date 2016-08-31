#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"Define all legal items and values for cylc suite definition files."

import re

from parsec.validate import validator as vdr
from parsec.validate import (
    coercers, _strip_and_unquote, _strip_and_unquote_list, IllegalValueError)
from parsec.util import itemstr
from parsec.upgrade import upgrader, converter
from parsec.config import config
from cylc.syntax_flags import (
    set_syntax_version, VERSION_PREV, VERSION_NEW, SyntaxVersionError)
from isodatetime.dumpers import TimePointDumper
from isodatetime.data import Calendar, TimePoint
from isodatetime.parsers import TimePointParser, DurationParser
from cylc.cycling.integer import REC_INTERVAL as REC_INTEGER_INTERVAL

from cylc.cfgspec.utils import (
    coerce_interval, coerce_interval_list, DurationFloat)
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.network import PRIVILEGE_LEVELS


REC_PARAM_INT_RANGE = re.compile('(\d+)\.\.(\d+)')


def _coerce_cycleinterval(value, keys, _):
    """Coerce value to a cycle interval."""
    if not value:
        return None
    value = _strip_and_unquote(keys, value)
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


def _coerce_cycletime(value, keys, _):
    """Coerce value to a cycle point."""
    if not value:
        return None
    if value == "now":
        # Handle this later in config.py when the suite UTC mode is known.
        return value
    value = _strip_and_unquote(keys, value)
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


def _coerce_cycletime_format(value, keys, _):
    """Coerce value to a cycle point format (either CCYYMM... or %Y%m...)."""
    value = _strip_and_unquote(keys, value)
    if not value:
        return None
    try:
        set_syntax_version(VERSION_NEW, "use of [cylc]cycle point format")
    except SyntaxVersionError:
        raise IllegalValueError("cycle point format", keys, value)
    test_timepoint = TimePoint(year=2001, month_of_year=3, day_of_month=1,
                               hour_of_day=4, minute_of_hour=30,
                               second_of_minute=54)
    if "/" in value:
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


def _coerce_cycletime_time_zone(value, keys, _):
    """Coerce value to a cycle point time zone format - Z, +13, -0800..."""
    value = _strip_and_unquote(keys, value)
    if not value:
        return None
    try:
        set_syntax_version(
            VERSION_NEW, "use of [cylc]cycle point time zone format")
    except SyntaxVersionError:
        raise IllegalValueError("cycle point time zone format", keys, value)
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


def _coerce_final_cycletime(value, keys, _):
    """Coerce final cycle point."""
    return _strip_and_unquote(keys, value)


def _coerce_parameter_list(value, keys, _):
    """Coerce parameter list."""
    value = _strip_and_unquote_list(keys, value)
    if len(value) == 1:
        # May be a range e.g. '1..5' (bounds inclusive)
        try:
            lower, upper = REC_PARAM_INT_RANGE.match(value[0]).groups()
        except AttributeError:
            if '.' in value[0]:
                # Dot is illegal in node names, probably bad range syntax.
                raise IllegalValueError("parameter", keys, value)
        else:
            n_dig = len(upper)
            return [
                str(i).zfill(n_dig) for i in range(int(lower), int(upper) + 1)]
    return value

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
coercers['parameter_list'] = _coerce_parameter_list


SPEC = {
    'title': vdr(vtype='string', default=""),
    'description': vdr(vtype='string', default=""),
    'URL': vdr(vtype='string', default=""),
    'cylc': {
        'UTC mode': vdr(
            vtype='boolean', default=GLOBAL_CFG.get(['cylc', 'UTC mode'])),
        'cycle point format': vdr(
            vtype='cycletime_format', default=None),
        'cycle point num expanded year digits': vdr(
            vtype='integer', default=0),
        'cycle point time zone': vdr(
            vtype='cycletime_time_zone', default=None),
        'required run mode': vdr(
            vtype='string', options=['live', 'dummy', 'simulation', '']),
        'force run mode': vdr(
            vtype='string', options=['live', 'dummy', 'simulation', '']),
        'abort if any task fails': vdr(vtype='boolean', default=False),
        'log resolved dependencies': vdr(vtype='boolean', default=False),
        'disable automatic shutdown': vdr(vtype='boolean', default=False),
        'environment': {
            '__MANY__': vdr(vtype='string'),
        },
        'parameters': {
            '__MANY__': vdr(vtype='parameter_list'),
        },
        'parameter templates': {
            '__MANY__': vdr(vtype='string'),
        },
        'events': {
            'handlers': vdr(vtype='string_list'),
            'handler events': vdr(vtype='string_list'),
            'startup handler': vdr(vtype='string_list'),
            'timeout handler': vdr(vtype='string_list'),
            'inactivity handler': vdr(vtype='string_list'),
            'shutdown handler': vdr(vtype='string_list'),
            'stalled handler': vdr(vtype='string_list'),
            'timeout': vdr(vtype='interval_minutes'),
            'inactivity': vdr(vtype='interval_minutes'),
            'reset timer': vdr(vtype='boolean', default=True),
            'reset inactivity timer': vdr(vtype='boolean', default=True),
            'abort if startup handler fails': vdr(
                vtype='boolean', default=False),
            'abort if shutdown handler fails': vdr(
                vtype='boolean', default=False),
            'abort if timeout handler fails': vdr(
                vtype='boolean', default=False),
            'abort if inactivity handler fails': vdr(
                vtype='boolean', default=False),
            'abort if stalled handler fails': vdr(
                vtype='boolean', default=False),
            'abort on stalled': vdr(vtype='boolean', default=None),
            'abort on timeout': vdr(vtype='boolean', default=None),
            'abort on inactivity': vdr(vtype='boolean'),
            'mail events': vdr(vtype='string_list'),
            'mail from': vdr(vtype='string'),
            'mail smtp': vdr(vtype='string'),
            'mail to': vdr(vtype='string'),
        },
        'simulation mode': {
            'disable suite event hooks': vdr(vtype='boolean', default=True),
        },
        'dummy mode': {
            'disable suite event hooks': vdr(vtype='boolean', default=True),
        },
        'reference test': {
            'suite shutdown event handler': vdr(
                vtype='string', default='cylc hook check-triggering'),
            'required run mode': vdr(
                vtype='string', options=['live', 'simulation', 'dummy', '']),
            'allow task failures': vdr(vtype='boolean', default=False),
            'expected task failures': vdr(vtype='string_list', default=[]),
            'live mode suite timeout': vdr(
                vtype='interval_minutes', default=DurationFloat(60)),
            'dummy mode suite timeout': vdr(
                vtype='interval_minutes', default=DurationFloat(60)),
            'simulation mode suite timeout': vdr(
                vtype='interval_minutes', default=DurationFloat(60)),
        },
        'authentication': {
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            'public': vdr(
                vtype='string',
                options=PRIVILEGE_LEVELS[
                    :PRIVILEGE_LEVELS.index('shutdown') + 1],
                default=GLOBAL_CFG.get(['authentication', 'public']))
        },
    },
    'scheduling': {
        'initial cycle point': vdr(vtype='cycletime'),
        'final cycle point': vdr(vtype='final_cycletime'),
        'initial cycle point constraints': vdr(
            vtype='string_list', default=[]),
        'final cycle point constraints': vdr(vtype='string_list', default=[]),
        'hold after point': vdr(vtype='cycletime'),
        'cycling mode': vdr(
            vtype='string',
            default=Calendar.MODE_GREGORIAN,
            options=(Calendar.MODES.keys() + ["integer"])),
        'runahead limit': vdr(vtype='cycleinterval'),
        'max active cycle points': vdr(vtype='integer', default=3),
        'spawn to max active cycle points': vdr(
            vtype='boolean', default=False),
        'queues': {
            'default': {
                'limit': vdr(vtype='integer', default=0),
                'members': vdr(vtype='string_list', default=[]),
            },
            '__MANY__': {
                'limit': vdr(vtype='integer', default=0),
                'members': vdr(vtype='string_list', default=[]),
            },
        },
        'special tasks': {
            'clock-trigger': vdr(vtype='string_list', default=[]),
            'external-trigger': vdr(vtype='string_list', default=[]),
            'clock-expire': vdr(vtype='string_list', default=[]),
            'sequential': vdr(vtype='string_list', default=[]),
            'exclude at start-up': vdr(vtype='string_list', default=[]),
            'include at start-up': vdr(vtype='string_list', default=[]),
        },
        'dependencies': {
            'graph': vdr(vtype='string'),
            '__MANY__':
            {
                'graph': vdr(vtype='string'),
            },
        },
    },
    'runtime': {
        '__MANY__': {
            'inherit': vdr(vtype='string_list', default=[]),
            'title': vdr(vtype='string', default=""),
            'description': vdr(vtype='string', default=""),
            'URL': vdr(vtype='string', default=""),
            'init-script': vdr(vtype='string'),
            'env-script': vdr(vtype='string'),
            'pre-script': vdr(vtype='string'),
            'script': vdr(
                vtype='string',
                default='echo Dummy task; sleep $(cylc rnd 1 16)'),
            'post-script': vdr(vtype='string'),
            'extra log files': vdr(vtype='string_list', default=[]),
            'enable resurrection': vdr(vtype='boolean', default=False),
            'work sub-directory': vdr(
                vtype='string',
                default='$CYLC_TASK_CYCLE_POINT/$CYLC_TASK_NAME'),
            'environment filter': {
                'include': vdr(vtype='string_list'),
                'exclude': vdr(vtype='string_list'),
            },
            'simulation mode': {
                'run time range': vdr(
                    vtype='interval_seconds_list',
                    default=[DurationFloat(1), DurationFloat(16)]),
                'simulate failure': vdr(vtype='boolean', default=False),
                'disable task event hooks': vdr(vtype='boolean', default=True),
                'disable retries': vdr(vtype='boolean', default=True),
            },
            'dummy mode': {
                'script': vdr(
                    vtype='string',
                    default='echo Dummy task; sleep $(cylc rnd 1 16)'),
                'disable pre-script': vdr(vtype='boolean', default=True),
                'disable post-script': vdr(vtype='boolean', default=True),
                'disable task event hooks': vdr(vtype='boolean', default=True),
                'disable retries': vdr(vtype='boolean', default=True),
            },
            'job': {
                'batch system': vdr(vtype='string', default='background'),
                'batch submit command template': vdr(vtype='string'),
                'execution polling intervals': vdr(
                    vtype='interval_minutes_list', default=[]),
                'execution retry delays': vdr(
                    vtype='interval_minutes_list', default=[]),
                'execution time limit': vdr(vtype='interval_seconds'),
                'shell': vdr(vtype='string', default='/bin/bash'),
                'submission polling intervals': vdr(
                    vtype='interval_minutes_list', default=[]),
                'submission retry delays': vdr(
                    vtype='interval_minutes_list', default=[]),
            },
            'remote': {
                'host': vdr(vtype='string'),
                'owner': vdr(vtype='string'),
                'suite definition directory': vdr(vtype='string'),
                'retrieve job logs': vdr(vtype='boolean', default=None),
                'retrieve job logs max size': vdr(vtype='string'),
                'retrieve job logs retry delays': vdr(
                    vtype='interval_minutes_list'),
            },
            'events': {
                'execution timeout': vdr(vtype='interval_minutes'),
                'handlers': vdr(vtype='string_list'),
                'handler events': vdr(vtype='string_list'),
                'handler retry delays': vdr(vtype='interval_minutes_list'),
                'mail events': vdr(vtype='string_list'),
                'mail from': vdr(vtype='string'),
                'mail retry delays': vdr(vtype='interval_minutes_list'),
                'mail smtp': vdr(vtype='string'),
                'mail to': vdr(vtype='string'),
                'register job logs retry delays': vdr(
                    vtype='interval_minutes_list'),
                'reset timer': vdr(vtype='boolean', default=None),
                'submission timeout': vdr(vtype='interval_minutes'),

                'expired handler': vdr(vtype='string_list', default=[]),
                'submitted handler': vdr(vtype='string_list', default=[]),
                'started handler': vdr(vtype='string_list', default=[]),
                'succeeded handler': vdr(vtype='string_list', default=[]),
                'failed handler': vdr(vtype='string_list', default=[]),
                'submission failed handler': vdr(
                    vtype='string_list', default=[]),
                'warning handler': vdr(vtype='string_list', default=[]),
                'retry handler': vdr(vtype='string_list', default=[]),
                'submission retry handler': vdr(
                    vtype='string_list', default=[]),
                'execution timeout handler': vdr(
                    vtype='string_list', default=[]),
                'submission timeout handler': vdr(
                    vtype='string_list', default=[]),
            },
            'suite state polling': {
                'user': vdr(vtype='string'),
                'host': vdr(vtype='string'),
                'interval': vdr(vtype='interval_seconds'),
                'max-polls': vdr(vtype='integer'),
                'run-dir': vdr(vtype='string'),
                'template': vdr(vtype='string'),
                'verbose mode': vdr(vtype='boolean', default=None),
            },
            'environment': {
                '__MANY__': vdr(vtype='string'),
            },
            'directives': {
                '__MANY__': vdr(vtype='string'),
            },
            'outputs': {
                '__MANY__': vdr(vtype='string'),
            },
        },
    },
    'visualization': {
        'initial cycle point': vdr(vtype='cycletime'),
        'final cycle point': vdr(vtype='final_cycletime'),
        'number of cycle points': vdr(vtype='integer', default=3),
        'collapsed families': vdr(vtype='string_list', default=[]),
        'use node color for edges': vdr(vtype='boolean', default=False),
        'use node fillcolor for edges': vdr(vtype='boolean', default=False),
        'use node color for labels': vdr(vtype='boolean', default=False),
        'node penwidth': vdr(vtype='integer', default=2),
        'edge penwidth': vdr(vtype='integer', default=2),
        'default node attributes': vdr(
            vtype='string_list',
            default=['style=unfilled', 'color=black', 'shape=box']),
        'default edge attributes': vdr(
            vtype='string_list', default=['color=black']),
        'node groups': {
            '__MANY__': vdr(vtype='string_list', default=[]),
        },
        'node attributes': {
            '__MANY__': vdr(vtype='string_list', default=[]),
        },
    },
}


def upg(cfg, descr):
    """Upgrade old suite configuration."""
    u = upgrader(cfg, descr)
    u.deprecate(
        '5.2.0',
        ['cylc', 'event handler execution'],
        ['cylc', 'event handler submission'])
    # TODO - should abort if obsoleted items are encountered
    u.obsolete(
        '5.4.7', ['scheduling', 'special tasks', 'explicit restart outputs'])
    u.obsolete('5.4.11', ['cylc', 'accelerated clock'])
    u.obsolete('6.0.0', ['visualization', 'runtime graph'])
    u.obsolete('6.1.3', ['visualization', 'enable live graph movie'])
    u.obsolete('6.0.0', ['development'])
    u.deprecate(
        '6.0.0',
        ['scheduling', 'initial cycle time'],
        ['scheduling', 'initial cycle point'],
        converter(
            lambda x: x, 'changed naming to reflect non-date-time cycling'))
    u.deprecate(
        '6.0.0',
        ['scheduling', 'final cycle time'],
        ['scheduling', 'final cycle point'],
        converter(
            lambda x: x, 'changed naming to reflect non-date-time cycling'))
    u.deprecate(
        '6.0.0',
        ['visualization', 'initial cycle time'],
        ['visualization', 'initial cycle point'],
        converter(
            lambda x: x, 'changed naming to reflect non-date-time cycling'))
    u.deprecate(
        '6.0.0',
        ['visualization', 'final cycle time'],
        ['visualization', 'final cycle point'],
        converter(
            lambda x: x, 'changed naming to reflect non-date-time cycling'))
    u.deprecate(
        '6.0.0',
        ['scheduling', 'cycling']
    )
    u.deprecate(
        '6.0.0',
        ['scheduling', 'special tasks', 'sequential']
    )
    u.obsolete('6.0.0', ['cylc', 'job submission'])
    u.obsolete('6.0.0', ['cylc', 'event handler submission'])
    u.obsolete('6.0.0', ['cylc', 'poll and kill command submission'])
    u.obsolete('6.0.0', ['cylc', 'lockserver'])
    dep = {
        'pre-command scripting': 'pre-script',
        'command scripting': 'script',
        'post-command scripting': 'post-script',
        'environment scripting': 'env-script',
        'initial scripting': 'init-script'
    }
    for old, new in dep.items():
        u.deprecate(
            '6.4.0',
            ['runtime', '__MANY__', old],
            ['runtime', '__MANY__', new],
            silent=True)
        u.deprecate(
            '6.4.0',
            ['runtime', '__MANY__', 'dummy mode', old],
            ['runtime', '__MANY__', 'dummy mode', new],
            silent=True)
    u.deprecate(
        '6.5.0',
        ['scheduling', 'special tasks', 'clock-triggered'],
        ['scheduling', 'special tasks', 'clock-trigger'],
    )
    u.deprecate(
        '6.5.0',
        ['scheduling', 'special tasks', 'external-triggered'],
        ['scheduling', 'special tasks', 'external-trigger'],
    )
    for key in SPEC['cylc']['events']:
        u.deprecate(
            '6.10.3', ['cylc', 'event hooks', key], ['cylc', 'events', key])
    u.deprecate('6.10.3', ['cylc', 'event hooks'])
    for key in SPEC['runtime']['__MANY__']['events']:
        u.deprecate(
            '6.10.3',
            ['runtime', '__MANY__', 'event hooks', key],
            ['runtime', '__MANY__', 'events', key])
    u.deprecate('6.10.3', ['runtime', '__MANY__', 'event hooks'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'job submission', 'method'],
        ['runtime', '__MANY__', 'job', 'batch system'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'job submission', 'command template'],
        ['runtime', '__MANY__', 'job', 'batch submit command template'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'job submission', 'shell'],
        ['runtime', '__MANY__', 'job', 'shell'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'job submission', 'retry delays'],
        ['runtime', '__MANY__', 'job', 'submission retry delays'])
    u.deprecate('6.10.3', ['runtime', '__MANY__', 'job submission'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'retry delays'],
        ['runtime', '__MANY__', 'job', 'execution retry delays'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'submission polling intervals'],
        ['runtime', '__MANY__', 'job', 'submission polling intervals'])
    u.deprecate(
        '6.10.3',
        ['runtime', '__MANY__', 'execution polling intervals'],
        ['runtime', '__MANY__', 'job', 'execution polling intervals'])
    u.upgrade()
    if 'cylc' in cfg and 'event hooks' in cfg['cylc']:
        del cfg['cylc']['event hooks']
    if 'runtime' in cfg:
        for section in cfg['runtime'].values():
            for key in ['event hooks', 'job submission']:
                if key in section:
                    del section[key]

    # Force pre cylc-6 "cycling = Yearly" type suites to the explicit
    # dependency heading form for which backward compatibility is provided:
    # ___________________________
    # [scheduling]
    #    cycling = Yearly
    #    [[dependencies]]
    #        [[[2014,2]]]
    # ---------------------------
    # Same as (for auto upgrade):
    # ---------------------------
    # [scheduling]
    #    [[dependencies]]
    #        [[[Yearly(2014,2)]]]
    # ___________________________
    try:
        old_cycling_mode = cfg['scheduling']['cycling']
    except KeyError:
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


class RawSuiteConfig(config):
    """Raw suite configuration."""
    _SUITECFG = None
    _CFPATH = None

    @classmethod
    def get_inst(cls, fpath, force=False, tvars=None, write_proc=False):
        """Return the default instance."""
        if cls._SUITECFG is None or fpath != cls._CFPATH or force:
            cls._CFPATH = fpath
            if tvars is None:
                tvars = []
            # TODO - write_proc should be in loadcfg
            cls._SUITECFG = cls(SPEC, upg, tvars=tvars, write_proc=write_proc)
            cls._SUITECFG.loadcfg(fpath, "suite definition")
        return cls._SUITECFG
