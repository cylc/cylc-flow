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
"""Define all legal items and values for cylc suite definition files."""

import re

from metomi.isodatetime.data import Calendar


from cylc.flow import LOG
from cylc.flow.parsec.exceptions import UpgradeError
from cylc.flow.network.authorisation import Priv
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)
from cylc.flow.platform_lookup import reverse_lookup
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg

# Regex to check whether a string is a command
REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')

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
        'task event mail interval': [VDR.V_INTERVAL],
        'disable automatic shutdown': [VDR.V_BOOLEAN],
        'main loop': {
            '__MANY__': {
                'interval': [VDR.V_INTERVAL],
            }
        },
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
            'abort if any task fails': [VDR.V_BOOLEAN],
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
            'expected task failures': [VDR.V_STRING_LIST],
        },
        'authentication': {
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            'public': (
                [VDR.V_STRING, '']
                + [level.name.lower().replace('_', '-') for level in [
                    Priv.IDENTITY, Priv.DESCRIPTION, Priv.STATE_TOTALS,
                    Priv.READ, Priv.SHUTDOWN]])
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
            list(Calendar.MODES) + ["integer"]),
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
        'graph': {
            '__MANY__': [VDR.V_STRING],
        },
    },
    'runtime': {
        '__MANY__': {
            'platform': [VDR.V_STRING],
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
                'time limit buffer': [VDR.V_INTERVAL, DurationFloat(30)],
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
                # TODO All the remaining items to be moved to top level of TASK
                # When platforms work is completed.
                'execution polling intervals': [VDR.V_INTERVAL_LIST, None],
                'execution retry delays': [VDR.V_INTERVAL_LIST, None],
                'execution time limit': [VDR.V_INTERVAL],
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
    u.obsolete('7.2.2', ['cylc', 'dummy mode'])
    u.obsolete('7.2.2', ['cylc', 'simulation mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'dummy mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'simulation mode'])
    u.obsolete('7.6.0', ['runtime', '__MANY__', 'enable resurrection'])
    u.obsolete(
        '7.8.0',
        ['runtime', '__MANY__', 'suite state polling', 'template'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset inactivity timer'])
    u.obsolete('7.8.1', ['runtime', '__MANY__', 'events', 'reset timer'])
    u.obsolete('8.0.0', ['cylc', 'log resolved dependencies'])
    u.obsolete('8.0.0', ['cylc', 'reference test', 'allow task failures'])
    u.obsolete('8.0.0', ['cylc', 'reference test', 'live mode suite timeout'])
    u.obsolete('8.0.0', ['cylc', 'reference test', 'dummy mode suite timeout'])
    u.obsolete(
        '8.0.0',
        ['cylc', 'reference test', 'dummy-local mode suite timeout'])
    u.obsolete(
        '8.0.0',
        ['cylc', 'reference test', 'simulation mode suite timeout'])
    u.obsolete('8.0.0', ['cylc', 'reference test', 'required run mode'])
    u.obsolete(
        '8.0.0',
        ['cylc', 'reference test', 'suite shutdown event handler'])
    u.obsolete(
        '8.0.0',
        ['cylc', 'health check interval'])
    u.deprecate(
        '8.0.0',
        ['cylc', 'abort if any task fails'],
        ['cylc', 'events', 'abort if any task fails'])
    u.obsolete('8.0.0', ['runtime', '__MANY__', 'job', 'shell'])
    # TODO uncomment these deprecations when ready - see todo in
    # [runtime][__MANY__] section.
    # for job_setting in [
    #     'execution polling intervals',
    #     'execution retry delays',
    #     'execution time limit',
    #     'submission polling intervals',
    #     'submission retry delays'
    # ]:
    #     u.deprecate(
    #         '8.0.0',
    #         ['runtime', '__MANY__', 'job', job_setting],
    #         ['runtime', '__MANY__', job_setting]
    #     )
    # TODO - there are some simple changes to the config (items from [remote]
    # and [job] moved up 1 level for example) which should be upgraded here.
    u.upgrade()

    # Upgrader cannot do this type of move:
    try:  # Upgrade cfg['scheduling']['dependencies']['graph']
        if 'dependencies' in cfg['scheduling']:
            msg_old = '[scheduling][dependencies][X]graph'
            msg_new = '[scheduling][graph]X'
            if 'graph' in cfg['scheduling']:
                raise UpgradeError(
                    "Cannot upgrade deprecated item '{0} -> {1}' because "
                    "{2} already exists".format(msg_old, msg_new, msg_new[:-1])
                )
            else:
                keys = set()
                cfg['scheduling'].setdefault('graph', {})
                cfg['scheduling']['graph'].update(
                    cfg['scheduling'].pop('dependencies')
                )
                graphdict = cfg['scheduling']['graph']
                for key, value in graphdict.copy().items():
                    if isinstance(value, dict) and 'graph' in value:
                        graphdict[key] = value['graph']
                        keys.add(key)
                if keys:
                    LOG.warning(
                        "deprecated graph items were automatically upgraded "
                        "in '{0}':".format(descr)
                    )
                    LOG.warning(
                        ' * (8.0.0) {0} -> {1} - for X in:\n{2}'.format(
                            msg_old, msg_new, '\n'.join(sorted(keys))
                        )
                    )
    except KeyError:
        pass

    # TODO - uncomment this fn so that we actually use the host to platform
    # upgrader
    # cfg = host_to_platform(cfg)


def host_to_platform_upgrader(cfg):
    """Upgrade a config with host settings to a config with platform settings
    if it is appropriate to do so.

                       +-------------------------------+
                       | Is platform set in this       |
                       | [runtime][TASK]?              |
                       +-------------------------------+
                          |YES                      |NO
                          |                         |
    +---------------------v---------+      +--------+--------------+
    | Are any forbidden items set   |      | host == $(function)?  |
    | in any [runtime][TASK]        |      +-+---------------------+
    | [job] or [remote] section     |     NO |          |YES
    |                               |        |  +-------v------------------+
    +-------------------------------+        |  | Log - evaluate at task   |
              |YES            |NO            |  | submit                   |
              |               +-------+      |  |                          |
              |                       |      |  +--------------------------+
    +---------v---------------------+ |      |
    | Fail Loudly                   | |    +-v-----------------------------+
    +-------------------------------+ |    | * Run reverse_lookup()        |
                                      |    | * handle reverse lookup fail  |
                                      |    | * add platform                |
                                      |    | * delete forbidden settings   |
                                      |    +-------------------------------+
                                      |
                                      |    +-------------------------------+
                                      +----> Return without changes        |
                                           +-------------------------------+

    Args (cfg):
        config object to be upgraded

    Returns (cfg):
        upgraded config object
    """
    # If platform and old settings are set fail
    # and remote should be added to this forbidden list
    forbidden_with_platform = {
        'host', 'batch system', 'batch submit command template'
    }

    for task_name, task_spec in cfg['runtime'].items():
        # if task_name == 'delta':
        #     breakpoint(header=f"task_name = {task_name}")

        if (
            'platform' in task_spec and 'job' in task_spec or
            'platform' in task_spec and 'remote' in task_spec
        ):
            if (
                'platform' in task_spec and
                forbidden_with_platform & {
                    *task_spec['job'], *task_spec['remote']
                }
            ):
                # Fail Loudly and Horribly
                raise PlatformLookupError(
                    f"A mixture of Cylc 7 (host) and Cylc 8 (platform logic)"
                    f" should not be used. Task {task_name} set platform "
                    f"and item in {forbidden_with_platform}"
                )

        elif 'platform' in task_spec:
            # Return config unchanged
            continue

        else:
            # Add empty dicts if appropriate sections not present.
            if 'job' in task_spec:
                task_spec_job = task_spec['job']
            else:
                task_spec_job = {}
            if 'remote' in task_spec:
                task_spec_remote = task_spec['remote']
            else:
                task_spec_remote = {}

            # Deal with case where host is a function and we cannot auto
            # upgrade at the time of loading the config.
            if (
                'host' in task_spec_remote and
                REC_COMMAND.match(task_spec['remote']['host'])
            ):
                LOG.debug(
                    f"The host setting of '{task_name}' is a function: "
                    f"Cylc will try to upgrade this task on job submission."
                )
                continue

            # Attempt to use the reverse lookup
            try:
                platform = reverse_lookup(
                    glbl_cfg(cached=False).get(['job platforms']),
                    task_spec_job,
                    task_spec_remote
                )
            except PlatformLookupError as exc:
                raise PlatformLookupError(f"for task {task_name}: {exc}")
            else:
                # Set platform in config
                cfg['runtime'][task_name].update({'platform': platform})
                LOG.warning(f"Platform {platform} auto selected from ")
                # Remove deprecated items from config
                for old_spec_item in forbidden_with_platform:
                    for task_section in ['job', 'remote']:
                        if (
                            task_section in cfg['runtime'][task_name] and
                            old_spec_item in
                                cfg['runtime'][task_name][task_section].keys()
                        ):
                            poppable = cfg['runtime'][task_name][task_section]
                            poppable.pop(old_spec_item)
                    LOG.warning(
                        f"Cylc 7 {old_spec_item} removed."
                    )
    return cfg


class RawSuiteConfig(ParsecConfig):
    """Raw suite configuration."""

    def __init__(self, fpath, output_fname, tvars):
        """Return the default instance."""
        ParsecConfig.__init__(
            self, SPEC, upg, output_fname, tvars, cylc_config_validate)
        self.loadcfg(fpath, "suite definition")
