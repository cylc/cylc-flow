#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

from isodatetime.data import Calendar

from parsec import LOG
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.upgrade import upgrader
from parsec.config import ParsecConfig

from cylc.cfgvalidate import (
    cylc_config_validate, CylcConfigValidator as VDR, DurationFloat)
from cylc.network import PRIVILEGE_LEVELS, PRIV_SHUTDOWN


# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).
SPEC = {
    'meta': {
        'description': [VDR.V_STRING, ''],
        'group': [VDR.V_STRING, ''],
        'title': [VDR.V_STRING, ''],
        'URL': [VDR.V_STRING, ''],
        '__MANY__': [VDR.V_STRING, ''],
    },
    'cylc': {
        'UTC mode': [VDR.V_BOOLEAN, False],
        'cycle point format': [VDR.V_CYCLE_POINT_FORMAT],
        'cycle point num expanded year digits': [VDR.V_INTEGER, 0],
        'cycle point time zone': [VDR.V_CYCLE_POINT_TIME_ZONE],
        'required run mode': [
            VDR.V_STRING, '', 'live', 'dummy', 'dummy-local', 'simulation'],
        'force run mode': [
            VDR.V_STRING, '', 'live', 'dummy', 'dummy-local', 'simulation'],
        'abort if any task fails': [VDR.V_BOOLEAN],
        'health check interval': [VDR.V_INTERVAL],
        'task event mail interval': [VDR.V_INTERVAL],
        'log resolved dependencies': [VDR.V_BOOLEAN],
        'disable automatic shutdown': [VDR.V_BOOLEAN],
        'simulation': {
            'disable suite event handlers': [VDR.V_BOOLEAN, True],
        },
        'environment': {
            '__MANY__': [VDR.V_STRING],
        },
        'parameters': {
            '__MANY__': [VDR.V_PARAMETER_LIST],
        },
        'parameter templates': {
            '__MANY__': [VDR.V_STRING],
        },
        'events': {
            'handlers': [VDR.V_STRING_LIST, None],
            'handler events': [VDR.V_STRING_LIST, None],
            'startup handler': [VDR.V_STRING_LIST, None],
            'timeout handler': [VDR.V_STRING_LIST, None],
            'inactivity handler': [VDR.V_STRING_LIST, None],
            'shutdown handler': [VDR.V_STRING_LIST, None],
            'aborted handler': [VDR.V_STRING_LIST, None],
            'stalled handler': [VDR.V_STRING_LIST, None],
            'timeout': [VDR.V_INTERVAL],
            'inactivity': [VDR.V_INTERVAL],
            'abort if startup handler fails': [VDR.V_BOOLEAN],
            'abort if shutdown handler fails': [VDR.V_BOOLEAN],
            'abort if timeout handler fails': [VDR.V_BOOLEAN],
            'abort if inactivity handler fails': [VDR.V_BOOLEAN],
            'abort if stalled handler fails': [VDR.V_BOOLEAN],
            'abort on stalled': [VDR.V_BOOLEAN],
            'abort on timeout': [VDR.V_BOOLEAN],
            'abort on inactivity': [VDR.V_BOOLEAN],
            'mail events': [VDR.V_STRING_LIST, None],
            'mail from': [VDR.V_STRING],
            'mail smtp': [VDR.V_STRING],
            'mail to': [VDR.V_STRING],
            'mail footer': [VDR.V_STRING],
        },
        'reference test': {
            'suite shutdown event handler': [
                VDR.V_STRING, 'cylc hook check-triggering'],
            'required run mode': [
                VDR.V_STRING,
                '', 'live', 'simulation', 'dummy-local', 'dummy'],
            'allow task failures': [VDR.V_BOOLEAN],
            'expected task failures': [VDR.V_STRING_LIST],
            'live mode suite timeout': [
                VDR.V_INTERVAL, DurationFloat(60)],
            'dummy mode suite timeout': [
                VDR.V_INTERVAL, DurationFloat(60)],
            'dummy-local mode suite timeout': [
                VDR.V_INTERVAL, DurationFloat(60)],
            'simulation mode suite timeout': [
                VDR.V_INTERVAL, DurationFloat(60)],
        },
        'authentication': {
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            'public': (
                [VDR.V_STRING, ''] +
                PRIVILEGE_LEVELS[:PRIVILEGE_LEVELS.index(PRIV_SHUTDOWN) + 1]),
        },
    },
    'scheduling': {
        'initial cycle point': [VDR.V_CYCLE_POINT],
        'final cycle point': [VDR.V_STRING],
        'initial cycle point constraints': [VDR.V_STRING_LIST],
        'final cycle point constraints': [VDR.V_STRING_LIST],
        'hold after point': [VDR.V_CYCLE_POINT],
        'cycling mode': (
            [VDR.V_STRING, Calendar.MODE_GREGORIAN] +
            Calendar.MODES.keys() + ["integer"]),
        'runahead limit': [VDR.V_STRING],
        'max active cycle points': [VDR.V_INTEGER, 3],
        'spawn to max active cycle points': [VDR.V_BOOLEAN],
        'queues': {
            'default': {
                'limit': [VDR.V_INTEGER, 0],
                'members': [VDR.V_STRING_LIST],
            },
            '__MANY__': {
                'limit': [VDR.V_INTEGER, 0],
                'members': [VDR.V_STRING_LIST],
            },
        },
        'special tasks': {
            'clock-trigger': [VDR.V_STRING_LIST],
            'external-trigger': [VDR.V_STRING_LIST],
            'clock-expire': [VDR.V_STRING_LIST],
            'sequential': [VDR.V_STRING_LIST],
            'exclude at start-up': [VDR.V_STRING_LIST],
            'include at start-up': [VDR.V_STRING_LIST],
        },
        'xtriggers': {
            '__MANY__': [VDR.V_XTRIGGER],
        },
        'dependencies': {
            'graph': [VDR.V_STRING],
            '__MANY__':
            {
                'graph': [VDR.V_STRING],
            },
        },
    },
    'runtime': {
        '__MANY__': {
            'inherit': [VDR.V_STRING_LIST],
            'init-script': [VDR.V_STRING],
            'env-script': [VDR.V_STRING],
            'err-script': [VDR.V_STRING],
            'exit-script': [VDR.V_STRING],
            'pre-script': [VDR.V_STRING],
            'script': [VDR.V_STRING],
            'post-script': [VDR.V_STRING],
            'extra log files': [VDR.V_STRING_LIST],
            'work sub-directory': [VDR.V_STRING],
            'meta': {
                'title': [VDR.V_STRING, ''],
                'description': [VDR.V_STRING, ''],
                'URL': [VDR.V_STRING, ''],
                '__MANY__': [VDR.V_STRING, ''],
            },
            'simulation': {
                'default run length': [VDR.V_INTERVAL, DurationFloat(10)],
                'speedup factor': [VDR.V_FLOAT],
                'time limit buffer': [VDR.V_INTERVAL, DurationFloat(10)],
                'fail cycle points': [VDR.V_STRING_LIST],
                'fail try 1 only': [VDR.V_BOOLEAN, True],
                'disable task event handlers': [VDR.V_BOOLEAN, True],
            },
            'environment filter': {
                'include': [VDR.V_STRING_LIST],
                'exclude': [VDR.V_STRING_LIST],
            },
            'job': {
                'batch system': [VDR.V_STRING, 'background'],
                'batch submit command template': [VDR.V_STRING],
                'execution polling intervals': [VDR.V_INTERVAL_LIST, None],
                'execution retry delays': [VDR.V_INTERVAL_LIST, None],
                'execution time limit': [VDR.V_INTERVAL],
                'shell': [VDR.V_STRING, '/bin/bash'],
                'submission polling intervals': [VDR.V_INTERVAL_LIST, None],
                'submission retry delays': [VDR.V_INTERVAL_LIST, None],
            },
            'remote': {
                'host': [VDR.V_STRING],
                'owner': [VDR.V_STRING],
                'suite definition directory': [VDR.V_STRING],
                'retrieve job logs': [VDR.V_BOOLEAN],
                'retrieve job logs max size': [VDR.V_STRING],
                'retrieve job logs retry delays': [VDR.V_INTERVAL_LIST, None],
            },
            'events': {
                'execution timeout': [VDR.V_INTERVAL],
                'handlers': [VDR.V_STRING_LIST, None],
                'handler events': [VDR.V_STRING_LIST, None],
                'handler retry delays': [VDR.V_INTERVAL_LIST, None],
                'mail events': [VDR.V_STRING_LIST, None],
                'mail from': [VDR.V_STRING],
                'mail retry delays': [VDR.V_INTERVAL_LIST, None],
                'mail smtp': [VDR.V_STRING],
                'mail to': [VDR.V_STRING],
                'submission timeout': [VDR.V_INTERVAL],

                'expired handler': [VDR.V_STRING_LIST, None],
                'late offset': [VDR.V_INTERVAL, None],
                'late handler': [VDR.V_STRING_LIST, None],
                'submitted handler': [VDR.V_STRING_LIST, None],
                'started handler': [VDR.V_STRING_LIST, None],
                'succeeded handler': [VDR.V_STRING_LIST, None],
                'failed handler': [VDR.V_STRING_LIST, None],
                'submission failed handler': [VDR.V_STRING_LIST, None],
                'warning handler': [VDR.V_STRING_LIST, None],
                'critical handler': [VDR.V_STRING_LIST, None],
                'retry handler': [VDR.V_STRING_LIST, None],
                'submission retry handler': [VDR.V_STRING_LIST, None],
                'execution timeout handler': [VDR.V_STRING_LIST, None],
                'submission timeout handler': [VDR.V_STRING_LIST, None],
                'custom handler': [VDR.V_STRING_LIST, None],
            },
            'suite state polling': {
                'user': [VDR.V_STRING],
                'host': [VDR.V_STRING],
                'interval': [VDR.V_INTERVAL],
                'max-polls': [VDR.V_INTEGER],
                'message': [VDR.V_STRING],
                'run-dir': [VDR.V_STRING],
                'verbose mode': [VDR.V_BOOLEAN],
            },
            'environment': {
                '__MANY__': [VDR.V_STRING],
            },
            'directives': {
                '__MANY__': [VDR.V_STRING],
            },
            'outputs': {
                '__MANY__': [VDR.V_STRING],
            },
            'parameter environment templates': {
                # deprecated - see _upgrade_param_env_templates()
                '__MANY__': [VDR.V_STRING],
            },
        },
    },
    'visualization': {
        'initial cycle point': [VDR.V_CYCLE_POINT],
        'final cycle point': [VDR.V_STRING],
        'number of cycle points': [VDR.V_INTEGER, 3],
        'collapsed families': [VDR.V_STRING_LIST],
        'use node color for edges': [VDR.V_BOOLEAN],
        'use node fillcolor for edges': [VDR.V_BOOLEAN],
        'use node color for labels': [VDR.V_BOOLEAN],
        'node penwidth': [VDR.V_INTEGER, 2],
        'edge penwidth': [VDR.V_INTEGER, 2],
        'default node attributes': [
            VDR.V_STRING_LIST, ['style=unfilled', 'shape=ellipse']],
        'default edge attributes': [VDR.V_STRING_LIST],
        'node groups': {
            '__MANY__': [VDR.V_STRING_LIST],
        },
        'node attributes': {
            '__MANY__': [VDR.V_STRING_LIST],
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
    u.obsolete('7.8.0', ['runtime', '__MANY__', 'suite state polling',
                         'template'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset inactivity timer'])
    u.obsolete('7.8.1', ['runtime', '__MANY__', 'events', 'reset timer'])
    u.upgrade()

    _upgrade_param_env_templates(cfg, descr)


def _upgrade_param_env_templates(cfg, descr):
    """Prepend [runtime][X][parameter environment templates] contents to
    [runtime][X][environment]"""
    # `u.deprecate()` can't do this if [environment] already exists
    if 'runtime' in cfg:
        dep = "[runtime][%s][parameter environment templates]"
        new = "[runtime][%s][environment]"
        first_warn = True
        for task_name, task_items in cfg['runtime'].items():
            if 'parameter environment templates' not in task_items:
                continue
            if first_warn is True:
                LOG.warning(
                    "deprecated items automatically upgraded in '" + descr +
                    "':"
                )
                first_warn = False
            LOG.warning(
                " * (7.8.7) " + dep % task_name + " contents prepended to " +
                new % task_name
            )
            for key, val in reversed(
                    task_items['parameter environment templates'].items()):
                if 'environment' in task_items:
                    if key in task_items['environment']:
                        LOG.warning(
                            " *** " + dep % task_name + key + " ignored as " +
                            key + " already exists in " + new % task_name
                        )
                        continue
                else:
                    task_items['environment'] = OrderedDictWithDefaults()
                task_items['environment'].prepend(key, val)
            task_items.pop('parameter environment templates')


class RawSuiteConfig(ParsecConfig):
    """Raw suite configuration."""

    def __init__(self, fpath, output_fname, tvars):
        """Return the default instance."""
        ParsecConfig.__init__(
            self, SPEC, upg, output_fname, tvars, cylc_config_validate)
        self.loadcfg(fpath, "suite definition")
