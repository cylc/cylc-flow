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
from cylc.flow.parsec.config import ParsecConfig, ConfigNode as Conf
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)
from cylc.flow.platform_lookup import reverse_lookup
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg

# Regex to check whether a string is a command
REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')

with Conf('/') as SPEC:
    with Conf('meta'):
        Conf('description', VDR.V_STRING, '')
        Conf('group', VDR.V_STRING, '')
        Conf('title', VDR.V_STRING, '')
        Conf('URL', VDR.V_STRING, '')
        Conf('__MANY__', VDR.V_STRING, '')

    with Conf('cylc'):
        Conf('UTC mode', VDR.V_BOOLEAN, False)
        Conf('cycle point format', VDR.V_CYCLE_POINT_FORMAT)
        Conf('cycle point num expanded year digits', VDR.V_INTEGER, 0)
        Conf('cycle point time zone', VDR.V_CYCLE_POINT_TIME_ZONE)
        Conf('required run mode', VDR.V_STRING, '',
             options=['live', 'dummy', 'dummy-local', 'simulation'])
        Conf('force run mode', VDR.V_STRING, '',
             options=['live', 'dummy', 'dummy-local', 'simulation'])
        Conf('task event mail interval', VDR.V_INTERVAL)
        Conf('disable automatic shutdown', VDR.V_BOOLEAN)

        with Conf('main loop'):
            with Conf('__MANY__'):
                Conf('interval', VDR.V_INTERVAL)

        with Conf('simulation'):
            Conf('disable suite event handlers', VDR.V_BOOLEAN, True)

        with Conf('environment'):
            Conf('__MANY__', VDR.V_STRING)

        with Conf('parameters'):
            Conf('__MANY__', VDR.V_PARAMETER_LIST)

        with Conf('parameter templates'):
            Conf('__MANY__', VDR.V_STRING)

        with Conf('events'):
            Conf('handlers', VDR.V_STRING_LIST, None)
            Conf('handler events', VDR.V_STRING_LIST, None)
            Conf('startup handler', VDR.V_STRING_LIST, None)
            Conf('timeout handler', VDR.V_STRING_LIST, None)
            Conf('inactivity handler', VDR.V_STRING_LIST, None)
            Conf('shutdown handler', VDR.V_STRING_LIST, None)
            Conf('aborted handler', VDR.V_STRING_LIST, None)
            Conf('stalled handler', VDR.V_STRING_LIST, None)
            Conf('timeout', VDR.V_INTERVAL)
            Conf('inactivity', VDR.V_INTERVAL)
            Conf('abort if startup handler fails', VDR.V_BOOLEAN)
            Conf('abort if shutdown handler fails', VDR.V_BOOLEAN)
            Conf('abort if timeout handler fails', VDR.V_BOOLEAN)
            Conf('abort if inactivity handler fails', VDR.V_BOOLEAN)
            Conf('abort if stalled handler fails', VDR.V_BOOLEAN)
            Conf('abort if any task fails', VDR.V_BOOLEAN)
            Conf('abort on stalled', VDR.V_BOOLEAN)
            Conf('abort on timeout', VDR.V_BOOLEAN)
            Conf('abort on inactivity', VDR.V_BOOLEAN)
            Conf('mail events', VDR.V_STRING_LIST, None)
            Conf('mail from', VDR.V_STRING)
            Conf('mail smtp', VDR.V_STRING)
            Conf('mail to', VDR.V_STRING)
            Conf('mail footer', VDR.V_STRING)

        with Conf('reference test'):
            Conf('expected task failures', VDR.V_STRING_LIST)

        with Conf('authentication'):
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            Conf(
                'public',
                VDR.V_STRING, '',
                options=[
                    level.name.lower().replace('_', '-')
                    for level in [
                        Priv.IDENTITY, Priv.DESCRIPTION, Priv.STATE_TOTALS,
                        Priv.READ, Priv.SHUTDOWN
                    ]
                ]
            )

    with Conf('scheduling'):
        Conf('initial cycle point', VDR.V_CYCLE_POINT)
        Conf('final cycle point', VDR.V_STRING)
        Conf('initial cycle point constraints', VDR.V_STRING_LIST)
        Conf('final cycle point constraints', VDR.V_STRING_LIST)
        Conf('hold after point', VDR.V_CYCLE_POINT)
        Conf('cycling mode', VDR.V_STRING, Calendar.MODE_GREGORIAN,
             options=list(Calendar.MODES) + ['integer'])
        Conf('runahead limit', VDR.V_STRING)
        Conf('max active cycle points', VDR.V_INTEGER, 3)
        Conf('spawn to max active cycle points', VDR.V_BOOLEAN)

        with Conf('queues'):
            with Conf('default'):
                Conf('limit', VDR.V_INTEGER, 0)
                Conf('members', VDR.V_STRING_LIST)

            with Conf('__MANY__'):
                Conf('limit', VDR.V_INTEGER, 0)
                Conf('members', VDR.V_STRING_LIST)

        with Conf('special tasks'):
            Conf('clock-trigger', VDR.V_STRING_LIST)
            Conf('external-trigger', VDR.V_STRING_LIST)
            Conf('clock-expire', VDR.V_STRING_LIST)
            Conf('sequential', VDR.V_STRING_LIST)
            Conf('exclude at start-up', VDR.V_STRING_LIST)
            Conf('include at start-up', VDR.V_STRING_LIST)

        with Conf('xtriggers'):
            Conf('__MANY__', VDR.V_XTRIGGER)

        with Conf('graph'):
            Conf('__MANY__', VDR.V_STRING)

    with Conf('runtime'):
        with Conf('__MANY__'):
            Conf('platform', VDR.V_STRING)
            Conf('inherit', VDR.V_STRING_LIST)
            Conf('init-script', VDR.V_STRING)
            Conf('env-script', VDR.V_STRING)
            Conf('err-script', VDR.V_STRING)
            Conf('exit-script', VDR.V_STRING)
            Conf('pre-script', VDR.V_STRING)
            Conf('script', VDR.V_STRING)
            Conf('post-script', VDR.V_STRING)
            Conf('extra log files', VDR.V_STRING_LIST)
            Conf('work sub-directory', VDR.V_STRING)

            with Conf('meta'):
                Conf('title', VDR.V_STRING, '')
                Conf('description', VDR.V_STRING, '')
                Conf('URL', VDR.V_STRING, '')
                Conf('__MANY__', VDR.V_STRING, '')

            with Conf('simulation'):
                Conf('default run length', VDR.V_INTERVAL, DurationFloat(10))
                Conf('speedup factor', VDR.V_FLOAT)
                Conf('time limit buffer', VDR.V_INTERVAL, DurationFloat(30))
                Conf('fail cycle points', VDR.V_STRING_LIST)
                Conf('fail try 1 only', VDR.V_BOOLEAN, True)
                Conf('disable task event handlers', VDR.V_BOOLEAN, True)

            with Conf('environment filter'):
                Conf('include', VDR.V_STRING_LIST)
                Conf('exclude', VDR.V_STRING_LIST)

            with Conf('job'):
                Conf('batch system', VDR.V_STRING, 'background')
                Conf('batch submit command template', VDR.V_STRING)
                # TODO All the remaining items to be moved to top level of
                # TASK when platforms work is completed.
                Conf('execution polling intervals', VDR.V_INTERVAL_LIST, None)
                Conf('execution retry delays', VDR.V_INTERVAL_LIST, None)
                Conf('execution time limit', VDR.V_INTERVAL)
                Conf('submission polling intervals', VDR.V_INTERVAL_LIST, None)
                Conf('submission retry delays', VDR.V_INTERVAL_LIST, None)

            with Conf('remote'):
                Conf('host', VDR.V_STRING)
                Conf('owner', VDR.V_STRING)
                Conf('suite definition directory', VDR.V_STRING)
                Conf('retrieve job logs', VDR.V_BOOLEAN)
                Conf('retrieve job logs max size', VDR.V_STRING)
                Conf('retrieve job logs retry delays',
                     VDR.V_INTERVAL_LIST, None)

            with Conf('events'):
                Conf('execution timeout', VDR.V_INTERVAL)
                Conf('handlers', VDR.V_STRING_LIST, None)
                Conf('handler events', VDR.V_STRING_LIST, None)
                Conf('handler retry delays', VDR.V_INTERVAL_LIST, None)
                Conf('mail events', VDR.V_STRING_LIST, None)
                Conf('mail from', VDR.V_STRING)
                Conf('mail retry delays', VDR.V_INTERVAL_LIST, None)
                Conf('mail smtp', VDR.V_STRING)
                Conf('mail to', VDR.V_STRING)
                Conf('submission timeout', VDR.V_INTERVAL)
                Conf('expired handler', VDR.V_STRING_LIST, None)
                Conf('late offset', VDR.V_INTERVAL, None)
                Conf('late handler', VDR.V_STRING_LIST, None)
                Conf('submitted handler', VDR.V_STRING_LIST, None)
                Conf('started handler', VDR.V_STRING_LIST, None)
                Conf('succeeded handler', VDR.V_STRING_LIST, None)
                Conf('failed handler', VDR.V_STRING_LIST, None)
                Conf('submission failed handler', VDR.V_STRING_LIST, None)
                Conf('warning handler', VDR.V_STRING_LIST, None)
                Conf('critical handler', VDR.V_STRING_LIST, None)
                Conf('retry handler', VDR.V_STRING_LIST, None)
                Conf('submission retry handler', VDR.V_STRING_LIST, None)
                Conf('execution timeout handler', VDR.V_STRING_LIST, None)
                Conf('submission timeout handler', VDR.V_STRING_LIST, None)
                Conf('custom handler', VDR.V_STRING_LIST, None)

            with Conf('suite state polling'):
                Conf('user', VDR.V_STRING)
                Conf('host', VDR.V_STRING)
                Conf('interval', VDR.V_INTERVAL)
                Conf('max-polls', VDR.V_INTEGER)
                Conf('message', VDR.V_STRING)
                Conf('run-dir', VDR.V_STRING)
                Conf('verbose mode', VDR.V_BOOLEAN)

            with Conf('environment'):
                Conf('__MANY__', VDR.V_STRING)

            with Conf('directives'):
                Conf('__MANY__', VDR.V_STRING)

            with Conf('outputs'):
                Conf('__MANY__', VDR.V_STRING)

            with Conf('parameter environment templates'):
                Conf('__MANY__', VDR.V_STRING)

    with Conf('visualization'):
        Conf('initial cycle point', VDR.V_CYCLE_POINT)
        Conf('final cycle point', VDR.V_STRING)
        Conf('number of cycle points', VDR.V_INTEGER, 3)
        Conf('collapsed families', VDR.V_STRING_LIST)
        Conf('use node color for edges', VDR.V_BOOLEAN)
        Conf('use node fillcolor for edges', VDR.V_BOOLEAN)
        Conf('use node color for labels', VDR.V_BOOLEAN)
        Conf('node penwidth', VDR.V_INTEGER, 2)
        Conf('edge penwidth', VDR.V_INTEGER, 2)
        Conf('default node attributes', VDR.V_STRING_LIST,
             default=['style=unfilled', 'shape=ellipse'])
        Conf('default edge attributes', VDR.V_STRING_LIST)

        with Conf('node groups'):
            Conf('__MANY__', VDR.V_STRING_LIST)

        with Conf('node attributes'):
            Conf('__MANY__', VDR.V_STRING_LIST)


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
