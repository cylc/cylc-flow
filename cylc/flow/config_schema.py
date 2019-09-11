#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import os
import re

from metomi.isodatetime.data import Calendar

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.network.authorisation import Priv
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)
from cylc.flow.hostuserutil import get_user_home, is_remote_user

# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
SPEC = {
    'meta': {
        'description': [VDR.V_STRING, ''],
        'group': [VDR.V_STRING, ''],
        'title': [VDR.V_STRING, ''],
        'URL': [VDR.V_STRING, ''],
        '__MANY__': [VDR.V_STRING, ''],
    },
    'general': {
        'UTC mode': [VDR.V_BOOLEAN, False],
        'cycle point format': [VDR.V_CYCLE_POINT_FORMAT],
        'cycle point num expanded year digits': [VDR.V_INTEGER, 0],
        'cycle point time zone': [VDR.V_CYCLE_POINT_TIME_ZONE, 'Z'],
        'maximum size in bytes': [VDR.V_INTEGER, 1000000],
        'process pool size': [VDR.V_INTEGER, 4],
        'process pool timeout': [VDR.V_INTERVAL, DurationFloat(600)],
        'required run mode': [
            VDR.V_STRING, '', 'live', 'dummy', 'dummy-local',
            'simulation'
        ],
        'rolling archive length': [VDR.V_INTEGER, 5],
        'run directory rolling archive length': [VDR.V_INTEGER, -1],
        'force run mode': [
            VDR.V_STRING, '', 'live', 'dummy', 'dummy-local',
            'simulation'
        ],
        'health check interval': [VDR.V_INTERVAL, 1500],
        'task event mail interval': [VDR.V_INTERVAL, 300],
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
            'abort if any task fails': [VDR.V_BOOLEAN, False],
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
            'abort if any task fails': [VDR.V_BOOLEAN, False],
            'abort if startup handler fails': [VDR.V_BOOLEAN],
            'abort if shutdown handler fails': [VDR.V_BOOLEAN],
            'abort if timeout handler fails': [VDR.V_BOOLEAN],
            'abort if inactivity handler fails': [VDR.V_BOOLEAN],
            'abort if stalled handler fails': [VDR.V_BOOLEAN],
            'abort on stalled': [VDR.V_BOOLEAN],
            'abort on timeout': [VDR.V_BOOLEAN],
            'abort on inactivity': [VDR.V_BOOLEAN],
        },
        'reference test': {
            'expected task failures': [VDR.V_STRING_LIST],
        },
        'authorization': {
            # Allow owners to grant public shutdown rights at the most, not
            # full control.
            'public': (
                [VDR.V_STRING, '']
                + [level.name.lower().replace('_', '-') for level in [
                    Priv.IDENTITY, Priv.DESCRIPTION, Priv.STATE_TOTALS,
                    Priv.READ, Priv.SHUTDOWN]])
        },
    },
    'job platforms': {
        'default platform': {
            'run directory': [VDR.V_STRING, '$HOME/cylc-run'],
            'work directory': [VDR.V_STRING, '$HOME/cylc-run'],
            'task communication method': [
                VDR.V_STRING, 'zmq', 'ssh+zmq', 'poll'],
            'submission polling intervals': [VDR.V_INTERVAL_LIST],
            'execution polling intervals': [VDR.V_INTERVAL_LIST],
            'scp command': [
                VDR.V_STRING, 'scp -oBatchMode=yes -oConnectTimeout=10'],
            'ssh command': [
                VDR.V_STRING, 'ssh -oBatchMode=yes -oConnectTimeout=10'],
            'use login shell': [VDR.V_BOOLEAN, True],
            'login hosts': [VDR.V_STRING, None],
            'batch system': [VDR.V_STRING, None],
            'cylc executable': [VDR.V_STRING, 'cylc'],
            'global init-script': [VDR.V_STRING],
            'retrieve job logs': [VDR.V_BOOLEAN],
            'retrieve job logs command': [VDR.V_STRING, 'rsync -a'],
            'retrieve job logs max size': [VDR.V_STRING],
            'retrieve job logs retry delays': [VDR.V_INTERVAL_LIST],
            'task event handler retry delays': [VDR.V_INTERVAL_LIST],
            'tail command template': [
                VDR.V_STRING, 'tail -n +1 -F %(filename)s'],
            'batch systems': {
                'err tailer': [VDR.V_STRING],
                'out tailer': [VDR.V_STRING],
                'err viewer': [VDR.V_STRING],
                'out viewer': [VDR.V_STRING],
                'job name length maximum': [VDR.V_INTEGER],
                'execution time limit polling intervals': [
                    VDR.V_INTERVAL_LIST],
            },
        },
        '__MANY__': {
            'run directory': [VDR.V_STRING, ''],
            'work directory': [VDR.V_STRING, ''],
            'task communication method': [VDR.V_STRING, ''],
            'submission polling intervals': [VDR.V_STRING, ''],
            'execution polling intervals': [VDR.V_STRING, ''],
            'scp command': [VDR.V_STRING, ''],
            'ssh command': [VDR.V_STRING, ''],
            'use login shell': [VDR.V_STRING, ''],
            'login hosts': [VDR.V_STRING, ''],
            'batch system': [VDR.V_STRING, ''],
            'cylc executable': [VDR.V_STRING, ''],
            'global init-script': [VDR.V_STRING, ''],
            'copyable environment variables': [VDR.V_STRING, ''],
            'retrieve job logs': [VDR.V_STRING, ''],
            'retrieve job logs command': [VDR.V_STRING, ''],
            'retrieve job logs max size': [VDR.V_STRING, ''],
            'retrieve job logs retry delays': [VDR.V_STRING, ''],
            'task event handler retry delays': [VDR.V_STRING, ''],
            'tail command template': [VDR.V_STRING, ''],
            'batch systems': {
                '__MANY__': {
                    'err tailer': [VDR.V_STRING, ''],
                    'out tailer': [VDR.V_STRING, ''],
                    'err viewer': [VDR.V_STRING, ''],
                    'out viewer': [VDR.V_STRING, ''],
                    'job name length maximum': [VDR.V_STRING, ''],
                    'execution time limit polling intervals': [
                        VDR.V_STRING, ''
                    ],
                }
            }
        },
    },
    'email': {
        'mail events': [VDR.V_STRING_LIST, None],
        'mail from': [VDR.V_STRING],
        'mail smtp': [VDR.V_STRING],
        'mail to': [VDR.V_STRING],
        'mail footer': [VDR.V_STRING],
        'monitor': {
            'sort order': [VDR.V_STRING, 'definition', 'alphanumeric'],
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
            'inherit': [VDR.V_STRING_LIST],
            'init-script': [VDR.V_STRING],
            'env-script': [VDR.V_STRING],
            'err-script': [VDR.V_STRING],
            'exit-script': [VDR.V_STRING],
            'pre-script': [VDR.V_STRING],
            'script': [VDR.V_STRING],
            'post-script': [VDR.V_STRING],
            'extra log files': [VDR.V_STRING_LIST],
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
                'execution polling intervals': [VDR.V_INTERVAL_LIST, None],
                'execution retry delays': [VDR.V_INTERVAL_LIST, None],
                'execution time limit': [VDR.V_INTERVAL],
                'submission polling intervals': [
                    VDR.V_INTERVAL_LIST, None
                ],
            },
            'platform': [VDR.V_STRING],
            'remote': {
                'host': [VDR.V_STRING],
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
    'suite run platforms': {
        'run hosts': [VDR.V_SPACELESS_STRING_LIST],
        'run ports': [VDR.V_INTEGER_LIST, list(range(43001, 43101))],
        'condemned hosts': [VDR.V_ABSOLUTE_HOST_LIST],
        'auto restart delay': [VDR.V_INTERVAL],
        'run host select': {
            'rank': [VDR.V_STRING, 'random', 'load:1', 'load:5', 'load:15',
                     'memory', 'disk-space'],
            'thresholds': [VDR.V_STRING],
        },
        'suite host self-identification': {
            'method': [VDR.V_STRING, 'name', 'address', 'hardwired'],
            'target': [VDR.V_STRING, 'google.com'],
            'host': [VDR.V_STRING],
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
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).


def upg(cfg, descr):
    # Upgrade older suite configurations.
    u = upgrader(cfg, descr)
    u.obsolete('6.1.3', ['visualization', 'enable live graph movie'])
    u.obsolete('6.4.1', ['test battery', 'directives'])
    u.obsolete('6.11.0', ['state dump rolling archive length'])
    u.obsolete('7.2.2', ['cylc', 'dummy mode'])
    u.obsolete('7.2.2', ['cylc', 'simulation mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'dummy mode'])
    u.obsolete('7.2.2', ['runtime', '__MANY__', 'simulation mode'])
    u.obsolete('7.6.0', ['runtime', '__MANY__', 'enable resurrection'])
    u.obsolete('7.8.0', ['runtime', '__MANY__', 'suite state polling',
                         'template'])
    u.obsolete('7.8.0', ['suite logging', 'roll over at start-up'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['cylc', 'events', 'reset inactivity timer'])
    u.obsolete('7.8.1', ['runtime', '__MANY__', 'events', 'reset timer'])
    u.obsolete('7.8.1', ['documentation', 'local index'])
    u.obsolete('7.8.1', ['documentation', 'files', 'pdf user guide'])
    u.obsolete(
        '7.8.1',
        ['documentation', 'files', 'single-page html user guide']
    )
    u.deprecate(
        '7.8.1',
        ['documentation', 'files', 'multi-page html user guide'],
        ['documentation', 'local']
    )
    u.deprecate('8.0.0',
                ['documentation', 'files', 'html index'],
                ['documentation', 'local']
                )
    u.deprecate(
        '8.0.0',
        ['documentation', 'urls', 'internet homepage'],
        ['documentation', 'cylc homepage']
    )
    u.deprecate('8.0.0', ['suite definition directory'])
    u.obsolete('8.0.0', ['communication'])
    u.deprecate('8.0.0', ['cylc', 'authentication'], ['cylc', 'authorization'])
    u.deprecate('8.0.0', ['cylc'], ['general'])
    u.obsolete('8.0.0', ['enable run directory housekeeping'])

    u.obsolete('8.0.0', ['runtime', '__MANY__', 'job', 'shell'])
    u.deprecate(
        '8.0.0',
        ['suite host self-identification'],
        ['suite run platforms', 'suite host self-identification']
    )
    u.obsolete('8.0.0', ['suite servers', 'scan hosts'])
    u.obsolete('8.0.0', ['suite servers', 'scan ports'])
    u.deprecate('8.0.0', ['suite servers'], ['suite run platforms'])
    u.deprecate('8.0.0', ['task events'], ['runtime', 'root', 'events'])
    u.obsolete('8.0.0', ['temporary directory'])
    u.obsolete('8.0.0', ['test battery'])
    u.obsolete('8.0.0', ['task host select command timeout'])
    u.obsolete('8.0.0', ['xtrigger function timeout'])
    u.deprecate(
        '8.0.0',
        ['general', 'authentication'],
        ['general', 'authorization']
    )
    u.upgrade()

    # Upgrader cannot do this type of move.
    try:
        keys = set()
        cfg['scheduling'].setdefault('graph', {})
        cfg['scheduling']['graph'].update(
            cfg['scheduling'].pop('dependencies'))
        graphdict = cfg['scheduling']['graph']
        for key, value in graphdict.copy().items():
            if isinstance(value, dict) and 'graph' in value:
                graphdict[key] = value['graph']
                keys.add(key)
        if keys:
            LOG.warning(
                "deprecated graph items were automatically upgraded in '%s':",
                descr)
            LOG.warning(
                ' * (8.0.0) %s -> %s - for X in:\n%s',
                u.show_keys(['scheduling', 'dependencies', 'X', 'graph']),
                u.show_keys(['scheduling', 'graph', 'X']),
                '\n'.join(sorted(keys)),
            )
    except KeyError:
        pass


class RawSuiteConfig(ParsecConfig):
    """Raw suite configuration."""

    def __init__(self, fpath, output_fname, tvars):
        """Return the default instance."""
        ParsecConfig.__init__(
            self, SPEC, upg, output_fname, tvars, cylc_config_validate)
        self.loadcfg(fpath, "suite definition")


class GlobalConfig(ParsecConfig):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.
    """

    _DEFAULT = None
    _HOME = os.getenv('HOME') or get_user_home()
    CONF_BASENAME = "cylc-flow.rc"
    SITE_CONF_DIR = os.path.join(os.sep, 'etc', 'cylc', 'flow', CYLC_VERSION)
    USER_CONF_DIR = os.path.join(_HOME, '.cylc', 'flow', CYLC_VERSION)

    @classmethod
    def get_inst(cls, cached=True):
        """Return a GlobalConfig instance.

        Args:
            cached (bool):
                If cached create if necessary and return the singleton
                instance, else return a new instance.
        """
        if not cached:
            # Return an up-to-date global config without affecting the
            # singleton.
            new_instance = cls(SPEC, upg, validator=cylc_config_validate)
            new_instance.load()
            return new_instance
        elif not cls._DEFAULT:
            cls._DEFAULT = cls(SPEC, upg, validator=cylc_config_validate)
            cls._DEFAULT.load()
        return cls._DEFAULT

    def load(self):
        """Load or reload configuration from files."""
        self.sparse.clear()
        self.dense.clear()
        LOG.debug("Loading site/user config files")
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str:
            # Explicit config file override.
            fname = os.path.join(conf_path_str, self.CONF_BASENAME)
            if os.access(fname, os.F_OK | os.R_OK):
                self.loadcfg(fname, upgrader.USER_CONFIG)
        elif conf_path_str is None:
            # Use default locations.
            for conf_dir, conf_type in [
                    (self.SITE_CONF_DIR, upgrader.SITE_CONFIG),
                    (self.USER_CONF_DIR, upgrader.USER_CONFIG)]:
                fname = os.path.join(conf_dir, self.CONF_BASENAME)
                if not os.access(fname, os.F_OK | os.R_OK):
                    continue
                try:
                    self.loadcfg(fname, conf_type)
                except ParsecError as exc:
                    if conf_type == upgrader.SITE_CONFIG:
                        # Warn on bad site file (users can't fix it).
                        LOG.warning(
                            'ignoring bad %s %s:\n%s', conf_type, fname, exc)
                    else:
                        # Abort on bad user file (users can fix it).
                        LOG.error('bad %s %s', conf_type, fname)
                        raise
        # (OK if no flow.rc is found, just use system defaults).
        self._transform()

    def get_host_item(self, item, platform=None, owner=None,
                      replace_home=False, owner_home=None):
        """This allows hosts with no matching entry in the config file
        to default to appropriately modified localhost settings."""

        cfg = self.get()

        # (this may be called with explicit None values for localhost
        # and owner, so we can't use proper defaults in the arg list)
        if not platform:
            # if no platform is given the caller is asking about localhost
            platform = 'default platform'

        # is there a matching host section?
        platform_key = None
        if platform in cfg['job platforms']:
            # there's an entry for this platform
            platform_key = platform
        else:
            # try for a pattern match
            for cfg_host in cfg['job platforms']:
                if re.match(cfg_host, platform):
                    platform_key = cfg_host
                    break
        modify_dirs = False
        if platform_key is not None:
            # entry exists, any unset items under it have already
            # defaulted to modified localhost values (see site cfgspec)
            value = cfg['job platforms'][platform_key][item]
        else:
            # no entry so default to localhost and modify appropriately
            value = cfg['job platforms']['default platform'][item]
            modify_dirs = True
        if value and 'directory' in item:
            if replace_home or modify_dirs:
                # Replace local home dir with $HOME for eval'n on other host.
                value = value.replace(self._HOME, '$HOME')
            elif is_remote_user(owner):
                # Replace with ~owner for direct access via local filesys
                # (works for standard cylc-run directory location).
                if owner_home is None:
                    owner_home = os.path.expanduser('~%s' % owner)
                value = value.replace(self._HOME, owner_home)
        if item == "task communication method" and value == "default":
            # Translate "default" to client-server comms: "zmq"
            value = 'zmq'
        return value

    def _transform(self):
        """Transform various settings.

        Host item values of None default to modified localhost values.
        Expand environment variables and ~ notations.

        Ensure os.environ['HOME'] is defined with the correct value.
        """
        cfg = self.get()
        for platform in cfg['job platforms']:
            if platform == 'default platform':
                continue
            for item, value in cfg['job platforms'][platform].items():
                if value is not None:
                    newvalue = cfg['job platforms']['default platform'][item]
                else:
                    newvalue = value
                if newvalue and 'directory' in item:
                    # replace local home dir with $HOME for evaluation on other
                    # host
                    newvalue = newvalue.replace(self._HOME, '$HOME')
                cfg['job platforms'][platform][item] = newvalue

        # Expand environment variables and ~user in LOCAL file paths.
        if 'HOME' not in os.environ:
            os.environ['HOME'] = self._HOME
        cfg['documentation']['local'] = os.path.expandvars(
            cfg['documentation']['local'])
        for key, val in cfg['job platforms']['default platform'].items():
            if val and 'directory' in key:
                cfg['job platforms']['default platform'][key] =\
                    os.path.expandvars(val)
