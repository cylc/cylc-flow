#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
from parsec.upgrade import upgrader
from parsec.config import config
from isodatetime.dumpers import TimePointDumper
from isodatetime.data import Calendar, TimePoint
from isodatetime.parsers import TimePointParser, DurationParser

from cylc.cfgspec.utils import (
    coerce_interval, coerce_interval_list, DurationFloat)
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.network import PRIVILEGE_LEVELS, PRIV_SHUTDOWN
from cylc.task_id import TaskID


REC_PARAM_INT_RANGE = re.compile(
    r'\A([\+\-]?\d+)\.\.([\+\-]?\d+)(?:\.\.(\d+))?\Z')


def _coerce_cycleinterval(value, keys, _):
    """Coerce value to a cycle interval."""
    if not value:
        return None
    value = _strip_and_unquote(keys, value)
    parser = DurationParser()
    try:
        parser.parse(value)
    except ValueError:
        raise IllegalValueError("interval", keys, value)
    return value


def _coerce_cycletime(value, keys, _):
    """Coerce value to a cycle point."""
    if not value:
        return None
    value = _strip_and_unquote(keys, value)
    if value == "now":
        # Handle this later in config.py when the suite UTC mode is known.
        return value
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
    return value


def _coerce_cycletime_format(value, keys, _):
    """Coerce value to a cycle point format (either CCYYMM... or %Y%m...)."""
    value = _strip_and_unquote(keys, value)
    if not value:
        return None
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
    """Coerce parameter list

    Can be:
    * A list of str values. Each str value must conform to the same restriction
      as a task name. Return list of str values.
    * A mixture of int ranges and int values. Return list of str values
      containing the sorted int list, zero-padded to the same width.

    Raise IllegalValueError if:
    * Mixing str and int range.
    * A str value breaks the task name restriction.
    """
    items = []
    can_only_be = None   # A flag to prevent mixing str and int range
    for item in _strip_and_unquote_list(keys, value):
        match = REC_PARAM_INT_RANGE.match(item)
        if match:
            if can_only_be == str:
                raise IllegalValueError(
                    'parameter', keys, value, 'mixing int range and str')
            can_only_be = int
            lower, upper, step = match.groups()
            if not step:
                step = 1
            items.extend(range(int(lower), int(upper) + 1, int(step)))
        elif TaskID.NAME_SUFFIX_REC.match(item):
            if not item.isdigit():
                if can_only_be == int:
                    raise IllegalValueError(
                        'parameter', keys, value, 'mixing int range and str')
                can_only_be = str
            items.append(item)
        else:
            raise IllegalValueError(
                'parameter', keys, value, '%s: bad value' % item)
    if not items or can_only_be == str or any(
            not str(item).isdigit() for item in items):
        return items
    else:
        return [int(item) for item in items]


coercers['cycletime'] = _coerce_cycletime
coercers['cycletime_format'] = _coerce_cycletime_format
coercers['cycletime_time_zone'] = _coerce_cycletime_time_zone
coercers['cycleinterval'] = _coerce_cycleinterval
coercers['final_cycletime'] = _coerce_final_cycletime
coercers['interval'] = coerce_interval
coercers['interval_list'] = coerce_interval_list
coercers['parameter_list'] = _coerce_parameter_list


SPEC = {
    'meta': {
        'description': vdr(vtype='string', default=""),
        'group': vdr(vtype='string', default=""),
        'title': vdr(vtype='string', default=""),
        'URL': vdr(vtype='string', default=""),
        '__MANY__': vdr(vtype='string', default=""),
    },
    'cylc': {
        'UTC mode': vdr(
            vtype='boolean', default=glbl_cfg().get(['cylc', 'UTC mode'])),
        'cycle point format': vdr(
            vtype='cycletime_format', default=None),
        'cycle point num expanded year digits': vdr(
            vtype='integer', default=0),
        'cycle point time zone': vdr(
            vtype='cycletime_time_zone', default=None),
        'required run mode': vdr(
            vtype='string',
            options=['live', 'dummy', 'dummy-local', 'simulation', '']),
        'force run mode': vdr(
            vtype='string',
            options=['live', 'dummy', 'dummy-local', 'simulation', '']),
        'abort if any task fails': vdr(vtype='boolean', default=False),
        'health check interval': vdr(vtype='interval', default=None),
        'task event mail interval': vdr(vtype='interval', default=None),
        'log resolved dependencies': vdr(vtype='boolean', default=False),
        'disable automatic shutdown': vdr(vtype='boolean', default=False),
        'simulation': {
            'disable suite event handlers': vdr(vtype='boolean', default=True),
        },
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
            'timeout': vdr(vtype='interval'),
            'inactivity': vdr(vtype='interval'),
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
            'mail footer': vdr(vtype='string'),
        },
        'reference test': {
            'suite shutdown event handler': vdr(
                vtype='string', default='cylc hook check-triggering'),
            'required run mode': vdr(
                vtype='string',
                options=['live', 'simulation', 'dummy-local', 'dummy', '']),
            'allow task failures': vdr(vtype='boolean', default=False),
            'expected task failures': vdr(vtype='string_list', default=[]),
            'live mode suite timeout': vdr(
                vtype='interval', default=DurationFloat(60)),
            'dummy mode suite timeout': vdr(
                vtype='interval', default=DurationFloat(60)),
            'dummy-local mode suite timeout': vdr(
                vtype='interval', default=DurationFloat(60)),
            'simulation mode suite timeout': vdr(
                vtype='interval', default=DurationFloat(60)),
        },
        'authentication': {
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            'public': vdr(
                vtype='string',
                options=PRIVILEGE_LEVELS[
                    :PRIVILEGE_LEVELS.index(PRIV_SHUTDOWN) + 1],
                default=glbl_cfg().get(['authentication', 'public']))
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
            'init-script': vdr(vtype='string', default=""),
            'env-script': vdr(vtype='string', default=""),
            'err-script': vdr(vtype='string', default=""),
            'pre-script': vdr(vtype='string', default=""),
            'script': vdr(vtype='string', default=""),
            'post-script': vdr(vtype='string', default=""),
            'extra log files': vdr(vtype='string_list', default=[]),
            'work sub-directory': vdr(vtype='string'),
            'meta': {
                'title': vdr(vtype='string', default=""),
                'description': vdr(vtype='string', default=""),
                'URL': vdr(vtype='string', default=""),
                '__MANY__': vdr(vtype='string', default=""),
            },
            'simulation': {
                'default run length': vdr(vtype='interval', default='PT10S'),
                'speedup factor': vdr(vtype='float', default=None),
                'time limit buffer': vdr(vtype='interval', default='PT10S'),
                'fail cycle points': vdr(vtype='string_list', default=[]),
                'fail try 1 only': vdr(vtype='boolean', default=True),
                'disable task event handlers': vdr(
                    vtype='boolean', default=True),
            },
            'environment filter': {
                'include': vdr(vtype='string_list'),
                'exclude': vdr(vtype='string_list'),
            },
            'job': {
                'batch system': vdr(vtype='string', default='background'),
                'batch submit command template': vdr(vtype='string'),
                'execution polling intervals': vdr(
                    vtype='interval_list'),
                'execution retry delays': vdr(
                    vtype='interval_list', default=[]),
                'execution time limit': vdr(vtype='interval'),
                'shell': vdr(vtype='string', default='/bin/bash'),
                'submission polling intervals': vdr(
                    vtype='interval_list'),
                'submission retry delays': vdr(
                    vtype='interval_list', default=[]),
            },
            'remote': {
                'host': vdr(vtype='string'),
                'owner': vdr(vtype='string'),
                'suite definition directory': vdr(vtype='string'),
                'retrieve job logs': vdr(vtype='boolean', default=None),
                'retrieve job logs max size': vdr(vtype='string'),
                'retrieve job logs retry delays': vdr(
                    vtype='interval_list'),
            },
            'events': {
                'execution timeout': vdr(vtype='interval'),
                'handlers': vdr(vtype='string_list'),
                'handler events': vdr(vtype='string_list'),
                'handler retry delays': vdr(vtype='interval_list'),
                'mail events': vdr(vtype='string_list'),
                'mail from': vdr(vtype='string'),
                'mail retry delays': vdr(vtype='interval_list'),
                'mail smtp': vdr(vtype='string'),
                'mail to': vdr(vtype='string'),
                'reset timer': vdr(vtype='boolean', default=None),
                'submission timeout': vdr(vtype='interval'),

                'expired handler': vdr(vtype='string_list'),
                'submitted handler': vdr(vtype='string_list'),
                'started handler': vdr(vtype='string_list'),
                'succeeded handler': vdr(vtype='string_list'),
                'failed handler': vdr(vtype='string_list'),
                'submission failed handler': vdr(vtype='string_list'),
                'warning handler': vdr(vtype='string_list'),
                'critical handler': vdr(vtype='string_list'),
                'retry handler': vdr(vtype='string_list'),
                'submission retry handler': vdr(vtype='string_list'),
                'execution timeout handler': vdr(vtype='string_list'),
                'submission timeout handler': vdr(vtype='string_list'),
                'custom handler': vdr(vtype='string_list'),
            },
            'suite state polling': {
                'user': vdr(vtype='string'),
                'host': vdr(vtype='string'),
                'interval': vdr(vtype='interval'),
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
            'parameter environment templates': {
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
    u.obsolete('6.1.3', ['visualization', 'enable live graph movie'])
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
            ['runtime', '__MANY__', new])
        u.deprecate(
            '6.4.0',
            ['runtime', '__MANY__', 'dummy mode', old],
            ['runtime', '__MANY__', 'dummy mode', new])
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
    u.deprecate(
        '6.11.0', ['cylc', 'event hooks'], ['cylc', 'events'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'event hooks'],
        ['runtime', '__MANY__', 'events'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'job submission'],
        ['runtime', '__MANY__', 'job'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'job', 'method'],
        ['runtime', '__MANY__', 'job', 'batch system'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'job', 'command template'],
        ['runtime', '__MANY__', 'job', 'batch submit command template'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'job', 'retry delays'],
        ['runtime', '__MANY__', 'job', 'submission retry delays'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'retry delays'],
        ['runtime', '__MANY__', 'job', 'execution retry delays'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'submission polling intervals'],
        ['runtime', '__MANY__', 'job', 'submission polling intervals'])
    u.deprecate(
        '6.11.0',
        ['runtime', '__MANY__', 'execution polling intervals'],
        ['runtime', '__MANY__', 'job', 'execution polling intervals'])
    u.deprecate(
        '7.5.0',
        ['runtime', '__MANY__', 'title'],
        ['runtime', '__MANY__', 'meta', 'title'])
    u.deprecate(
        '7.5.0',
        ['runtime', '__MANY__', 'description'],
        ['runtime', '__MANY__', 'meta', 'description'])
    u.deprecate(
        '7.5.0',
        ['runtime', '__MANY__', 'URL'],
        ['runtime', '__MANY__', 'meta', 'URL'])
    u.deprecate(
        '7.5.0',
        ['title'],
        ['meta', 'title'])
    u.deprecate(
        '7.5.0',
        ['description'],
        ['meta', 'description'])
    u.deprecate(
        '7.5.0',
        ['URL'],
        ['meta', 'URL'])
    u.deprecate(
        '7.6.0',
        ['group'],
        ['meta', 'group'])
    u.obsolete('7.2.2', ['cylc', 'dummy mode'])
    u.obsolete('7.2.2', ['cylc', 'simulation mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'dummy mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'simulation mode'])
    u.obsolete('7.6.0', ['runtime', '__MANY__', 'enable resurrection'])
    u.upgrade()


class RawSuiteConfig(config):
    """Raw suite configuration."""

    def __init__(self, fpath, output_fname, tvars):
        """Return the default instance."""
        config.__init__(self, SPEC, upg, output_fname, tvars)
        self.loadcfg(fpath, "suite definition")
