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
"""Cylc site and user configuration file spec."""

import os
import re

from cylc.flow import LOG
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.hostuserutil import get_user_home, is_remote_user
from cylc.flow.network.authorisation import Priv
from cylc.flow.parsec.config import ParsecConfig, ConfigNode as Conf
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    DurationFloat, CylcConfigValidator as VDR, cylc_config_validate)

# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).
with Conf('/') as SPEC:
    # suite
    Conf('process pool size', VDR.V_INTEGER, 4)
    Conf('process pool timeout', VDR.V_INTERVAL, DurationFloat(600))
    # client
    Conf('disable interactive command prompts', VDR.V_BOOLEAN, True)
    # suite
    Conf('run directory rolling archive length', VDR.V_INTEGER, -1)
    # suite
    with Conf('cylc'):
        Conf('UTC mode', VDR.V_BOOLEAN)
        Conf('task event mail interval', VDR.V_INTERVAL, DurationFloat(300))
        with Conf('events'):
            Conf('handlers', VDR.V_STRING_LIST)
            Conf('handler events', VDR.V_STRING_LIST)
            Conf('mail events', VDR.V_STRING_LIST)
            Conf('mail from', VDR.V_STRING)
            Conf('mail smtp', VDR.V_STRING)
            Conf('mail to', VDR.V_STRING)
            Conf('mail footer', VDR.V_STRING)
            Conf('startup handler', VDR.V_STRING_LIST)
            Conf('timeout handler', VDR.V_STRING_LIST)
            Conf('inactivity handler', VDR.V_STRING_LIST)
            Conf('shutdown handler', VDR.V_STRING_LIST)
            Conf('aborted handler', VDR.V_STRING_LIST)
            Conf('stalled handler', VDR.V_STRING_LIST)
            Conf('timeout', VDR.V_INTERVAL)
            Conf('inactivity', VDR.V_INTERVAL)
            Conf('abort on timeout', VDR.V_BOOLEAN)
            Conf('abort on inactivity', VDR.V_BOOLEAN)
            Conf('abort on stalled', VDR.V_BOOLEAN)

        with Conf('main loop'):
            Conf('plugins', VDR.V_STRING_LIST, ['health check'])
            with Conf('health check'):
                Conf('interval', VDR.V_INTERVAL, DurationFloat(600))
            with Conf('__MANY__'):
                Conf('interval', VDR.V_INTERVAL)

    # suite
    with Conf('suite logging'):
        Conf('rolling archive length', VDR.V_INTEGER, 5)
        Conf('maximum size in bytes', VDR.V_INTEGER, 1000000)

    # general
    with Conf('documentation'):
        Conf('local', VDR.V_STRING, '')
        Conf('online', VDR.V_STRING,
             'http://cylc.github.io/doc/built-sphinx/index.html')
        Conf('cylc homepage', VDR.V_STRING, 'http://cylc.github.io/')

    # general
    with Conf('document viewers'):
        Conf('html', VDR.V_STRING, 'firefox')

    # client
    with Conf('editors'):
        Conf('terminal', VDR.V_STRING, 'vim')
        Conf('gui', VDR.V_STRING, 'gvim -f')

    # job platforms
    with Conf('job platforms'):
        with Conf('__MANY__'):
            Conf('batch system', VDR.V_STRING, 'background')
            Conf('batch submit command template', VDR.V_STRING)
            Conf('shell', VDR.V_STRING, '/bin/bash')
            Conf('run directory', VDR.V_STRING, '$HOME/cylc-run')
            Conf('work directory', VDR.V_STRING, '$HOME/cylc-run')
            Conf('suite definition directory', VDR.V_STRING)
            Conf('task communication method',
                 VDR.V_STRING, 'zmq', options=['zmq', 'poll'])
            # TODO ensure that it is possible to over-ride the following three
            # settings in suite config.
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST)
            Conf('submission retry delays', VDR.V_INTERVAL_LIST, None)
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST)
            Conf('execution time limit polling intervals', VDR.V_INTERVAL_LIST)
            Conf('scp command',
                 VDR.V_STRING, 'scp -oBatchMode=yes -oConnectTimeout=10')
            Conf('ssh command',
                 VDR.V_STRING, 'ssh -oBatchMode=yes -oConnectTimeout=10')
            Conf('use login shell', VDR.V_BOOLEAN, True)
            Conf('remote hosts', VDR.V_STRING_LIST)
            Conf('cylc executable', VDR.V_STRING, 'cylc')
            Conf('global init-script', VDR.V_STRING)
            Conf('copyable environment variables', VDR.V_STRING_LIST, '')
            Conf('retrieve job logs', VDR.V_BOOLEAN)
            Conf('retrieve job logs command', VDR.V_STRING, 'rsync -a')
            Conf('retrieve job logs max size', VDR.V_STRING)
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST)
            Conf('task event handler retry delays', VDR.V_INTERVAL_LIST)
            Conf('tail command template',
                 VDR.V_STRING, 'tail -n +1 -F %(filename)s')
            Conf('err tailer', VDR.V_STRING)
            Conf('out tailer', VDR.V_STRING)
            Conf('err viewer', VDR.V_STRING)
            Conf('out viewer', VDR.V_STRING)
            Conf('job name length maximum', VDR.V_INTEGER)
            Conf('owner', VDR.V_STRING)

    # Platform Groups
    with Conf('platform groups'):
        with Conf('__MANY__'):
            Conf('platforms', VDR.V_STRING_LIST)

    # task
    with Conf('hosts'):
        with Conf('localhost'):
            Conf('run directory', VDR.V_STRING, '$HOME/cylc-run')
            Conf('work directory', VDR.V_STRING, '$HOME/cylc-run')
            Conf('task communication method',
                 VDR.V_STRING, 'default', 'ssh', 'poll')
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST)
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST)
            Conf('scp command',
                 VDR.V_STRING, 'scp -oBatchMode=yes -oConnectTimeout=10')
            Conf('ssh command',
                 VDR.V_STRING, 'ssh -oBatchMode=yes -oConnectTimeout=10')
            Conf('use login shell', VDR.V_BOOLEAN, True)
            Conf('cylc executable', VDR.V_STRING, 'cylc')
            Conf('global init-script', VDR.V_STRING)
            Conf('copyable environment variables', VDR.V_STRING_LIST)
            Conf('retrieve job logs', VDR.V_BOOLEAN)
            Conf('retrieve job logs command', VDR.V_STRING, 'rsync -a')
            Conf('retrieve job logs max size', VDR.V_STRING)
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST)
            Conf('task event handler retry delays', VDR.V_INTERVAL_LIST)
            Conf('tail command template',
                 VDR.V_STRING, 'tail -n +1 -F %(filename)s')
            with Conf('batch systems'):
                with Conf('__MANY__'):
                    Conf('err tailer', VDR.V_STRING)
                    Conf('out tailer', VDR.V_STRING)
                    Conf('err viewer', VDR.V_STRING)
                    Conf('out viewer', VDR.V_STRING)
                    Conf('job name length maximum', VDR.V_INTEGER)
                    Conf('execution time limit polling intervals',
                         VDR.V_INTERVAL_LIST)

        with Conf('__MANY__'):
            Conf('run directory', VDR.V_STRING)
            Conf('work directory', VDR.V_STRING)
            Conf('task communication method',
                 VDR.V_STRING, 'default', 'ssh', 'poll')
            Conf('submission polling intervals', VDR.V_INTERVAL_LIST)
            Conf('execution polling intervals', VDR.V_INTERVAL_LIST)
            Conf('scp command', VDR.V_STRING)
            Conf('ssh command', VDR.V_STRING)
            Conf('use login shell', VDR.V_BOOLEAN)
            Conf('cylc executable', VDR.V_STRING)
            Conf('global init-script', VDR.V_STRING)
            Conf('copyable environment variables', VDR.V_STRING_LIST)
            Conf('retrieve job logs', VDR.V_BOOLEAN)
            Conf('retrieve job logs command', VDR.V_STRING)
            Conf('retrieve job logs max size', VDR.V_STRING)
            Conf('retrieve job logs retry delays', VDR.V_INTERVAL_LIST)
            Conf('task event handler retry delays', VDR.V_INTERVAL_LIST)
            Conf('tail command template', VDR.V_STRING)
            with Conf('batch systems'):
                with Conf('__MANY__'):
                    Conf('err tailer', VDR.V_STRING)
                    Conf('out tailer', VDR.V_STRING)
                    Conf('out viewer', VDR.V_STRING)
                    Conf('err viewer', VDR.V_STRING)
                    Conf('job name length maximum', VDR.V_INTEGER)
                    Conf('execution time limit polling intervals',
                         VDR.V_INTERVAL_LIST)

    # task
    with Conf('task events'):
        Conf('execution timeout', VDR.V_INTERVAL)
        Conf('handlers', VDR.V_STRING_LIST)
        Conf('handler events', VDR.V_STRING_LIST)
        Conf('handler retry delays', VDR.V_INTERVAL_LIST, None)
        Conf('mail events', VDR.V_STRING_LIST)
        Conf('mail from', VDR.V_STRING)
        Conf('mail retry delays', VDR.V_INTERVAL_LIST)
        Conf('mail smtp', VDR.V_STRING)
        Conf('mail to', VDR.V_STRING)
        Conf('submission timeout', VDR.V_INTERVAL)

    # client
    with Conf('test battery'):
        Conf('remote host with shared fs', VDR.V_STRING)
        Conf('remote host', VDR.V_STRING)
        Conf('remote owner', VDR.V_STRING)
        with Conf('batch systems'):
            with Conf('__MANY__'):
                Conf('host', VDR.V_STRING)
                Conf('out viewer', VDR.V_STRING)
                Conf('err viewer', VDR.V_STRING)
                with Conf('directives'):
                    Conf('__MANY__', VDR.V_STRING)

    # suite
    with Conf('suite host self-identification'):
        Conf('method', VDR.V_STRING, 'name',
             options=['name', 'address', 'hardwired'])
        Conf('target', VDR.V_STRING, 'google.com')
        Conf('host', VDR.V_STRING)

    # suite
    with Conf('authentication'):
        # Allow owners to grant public shutdown rights at the most, not full
        # control.
        Conf(
            'public',
            VDR.V_STRING,
            default=Priv.STATE_TOTALS.name.lower().replace('_', '-'),
            options=[
                level.name.lower().replace('_', '-')
                for level in [
                    Priv.IDENTITY, Priv.DESCRIPTION,
                    Priv.STATE_TOTALS, Priv.READ, Priv.SHUTDOWN
                ]
            ]
        )

    # suite
    with Conf('suite servers'):
        Conf('run hosts', VDR.V_SPACELESS_STRING_LIST)
        Conf('run ports', VDR.V_INTEGER_LIST, list(range(43001, 43101)))
        Conf('condemned hosts', VDR.V_ABSOLUTE_HOST_LIST)
        Conf('auto restart delay', VDR.V_INTERVAL)
        Conf('ranking', VDR.V_STRING)


def upg(cfg, descr):
    """Upgrader."""
    u = upgrader(cfg, descr)

    u.obsolete('6.4.1', ['test battery', 'directives'])
    u.obsolete('6.11.0', ['state dump rolling archive length'])
    # Roll over is always done.
    u.obsolete('7.8.0', ['suite logging', 'roll over at start-up'])
    u.obsolete('7.8.1', ['documentation', 'local index'])
    u.obsolete('7.8.1', ['documentation', 'files', 'pdf user guide'])
    u.obsolete('7.8.1', ['documentation', 'files',
                         'single-page html user guide'])
    u.deprecate('7.8.1',
                ['documentation', 'files', 'multi-page html user guide'],
                ['documentation', 'local'])
    u.deprecate('8.0.0',
                ['documentation', 'files', 'html index'],
                ['documentation', 'local'])
    u.deprecate('8.0.0',
                ['documentation', 'urls', 'internet homepage'],
                ['documentation', 'cylc homepage'])
    u.obsolete('8.0.0', ['suite servers', 'scan hosts'])
    u.obsolete('8.0.0', ['suite servers', 'scan ports'])
    u.obsolete('8.0.0', ['communication'])
    u.obsolete('8.0.0', ['temporary directory'])
    u.obsolete('8.0.0', ['task host select command timeout'])
    u.obsolete('8.0.0', ['xtrigger function timeout'])
    u.obsolete('8.0.0', ['enable run directory housekeeping'])
    u.obsolete('8.0.0', ['task messaging'])

    u.upgrade()


class GlobalConfig(ParsecConfig):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.
    """

    _DEFAULT = None
    _HOME = os.getenv('HOME') or get_user_home()
    CONF_BASENAME = "flow.rc"
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

    def get_host_item(self, item, host=None, owner=None, replace_home=False,
                      owner_home=None):
        """This allows hosts with no matching entry in the config file
        to default to appropriately modified localhost settings."""

        cfg = self.get()

        # (this may be called with explicit None values for localhost
        # and owner, so we can't use proper defaults in the arg list)
        if not host:
            # if no host is given the caller is asking about localhost
            host = 'localhost'

        # is there a matching host section?
        host_key = None
        if host in cfg['hosts']:
            # there's an entry for this host
            host_key = host
        else:
            # try for a pattern match
            for cfg_host in cfg['hosts']:
                if re.match(cfg_host, host):
                    host_key = cfg_host
                    break
        modify_dirs = False
        if host_key is not None:
            # entry exists, any unset items under it have already
            # defaulted to modified localhost values (see site cfgspec)
            value = cfg['hosts'][host_key][item]
        else:
            # no entry so default to localhost and modify appropriately
            value = cfg['hosts']['localhost'][item]
            modify_dirs = True
        if value is not None and 'directory' in item:
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

        for host in cfg['hosts']:
            if host == 'localhost':
                continue
            for item, value in cfg['hosts'][host].items():
                if value is None:
                    newvalue = cfg['hosts']['localhost'][item]
                else:
                    newvalue = value
                if newvalue and 'directory' in item:
                    # replace local home dir with $HOME for evaluation on other
                    # host
                    newvalue = newvalue.replace(self._HOME, '$HOME')
                cfg['hosts'][host][item] = newvalue

        # Expand environment variables and ~user in LOCAL file paths.
        if 'HOME' not in os.environ:
            os.environ['HOME'] = self._HOME
        cfg['documentation']['local'] = os.path.expandvars(
            cfg['documentation']['local'])
        for key, val in cfg['hosts']['localhost'].items():
            if val and 'directory' in key:
                cfg['hosts']['localhost'][key] = os.path.expandvars(val)
