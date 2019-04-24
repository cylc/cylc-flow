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
"""Cylc site and user configuration file spec."""

import atexit
import os
import re
import shutil
from tempfile import mkdtemp

from parsec.config import ParsecConfig
from parsec.exceptions import ParsecError
from parsec.upgrade import upgrader

from cylc import LOG
from cylc.cfgvalidate import (
    cylc_config_validate, CylcConfigValidator as VDR, DurationFloat)
from cylc.exceptions import GlobalConfigError
from cylc.hostuserutil import get_user_home, is_remote_user
from cylc.network import Priv
from cylc import __version__ as CYLC_VERSION

# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).
SPEC = {
    'process pool size': [VDR.V_INTEGER, 4],
    'process pool timeout': [VDR.V_INTERVAL, DurationFloat(600)],
    'temporary directory': [VDR.V_STRING],
    'state dump rolling archive length': [VDR.V_INTEGER, 10],
    'disable interactive command prompts': [VDR.V_BOOLEAN, True],
    'enable run directory housekeeping': [VDR.V_BOOLEAN],
    'run directory rolling archive length': [VDR.V_INTEGER, 2],
    'task host select command timeout': [VDR.V_INTERVAL, DurationFloat(10)],
    'xtrigger function timeout': [VDR.V_INTERVAL, DurationFloat(10)],
    'task messaging': {
        'retry interval': [VDR.V_INTERVAL, DurationFloat(5)],
        'maximum number of tries': [VDR.V_INTEGER, 7],
        'connection timeout': [VDR.V_INTERVAL, DurationFloat(30)],
    },

    'cylc': {
        'UTC mode': [VDR.V_BOOLEAN],
        'health check interval': [VDR.V_INTERVAL, DurationFloat(600)],
        'task event mail interval': [VDR.V_INTERVAL, DurationFloat(300)],
        'events': {
            'handlers': [VDR.V_STRING_LIST],
            'handler events': [VDR.V_STRING_LIST],
            'mail events': [VDR.V_STRING_LIST],
            'mail from': [VDR.V_STRING],
            'mail smtp': [VDR.V_STRING],
            'mail to': [VDR.V_STRING],
            'mail footer': [VDR.V_STRING],
            'startup handler': [VDR.V_STRING_LIST],
            'timeout handler': [VDR.V_STRING_LIST],
            'inactivity handler': [VDR.V_STRING_LIST],
            'shutdown handler': [VDR.V_STRING_LIST],
            'stalled handler': [VDR.V_STRING_LIST],
            'timeout': [VDR.V_INTERVAL],
            'inactivity': [VDR.V_INTERVAL],
            'abort on timeout': [VDR.V_BOOLEAN],
            'abort on inactivity': [VDR.V_BOOLEAN],
            'abort on stalled': [VDR.V_BOOLEAN],
        },
    },

    'suite logging': {
        'rolling archive length': [VDR.V_INTEGER, 5],
        'maximum size in bytes': [VDR.V_INTEGER, 1000000],
    },

    'documentation': {
        'local': [VDR.V_STRING, '$CYLC_DIR/doc/built-sphinx/index.html'],
        'online': [VDR.V_STRING,
                   'http://cylc.github.io/doc/built-sphinx/index.html'],
        'cylc homepage': [VDR.V_STRING, 'http://cylc.github.io/'],
    },

    'document viewers': {
        'html': [VDR.V_STRING, 'firefox'],
    },

    'editors': {
        'terminal': [VDR.V_STRING, 'vim'],
        'gui': [VDR.V_STRING, 'gvim -f'],
    },

    'monitor': {
        'sort order': [VDR.V_STRING, 'definition', 'alphanumeric'],
    },

    'hosts': {
        'localhost': {
            'run directory': [VDR.V_STRING, '$HOME/cylc-run'],
            'work directory': [VDR.V_STRING, '$HOME/cylc-run'],
            'task communication method': [
                VDR.V_STRING, 'default', 'ssh', 'poll'],
            'submission polling intervals': [VDR.V_INTERVAL_LIST],
            'execution polling intervals': [VDR.V_INTERVAL_LIST],
            'scp command': [
                VDR.V_STRING, 'scp -oBatchMode=yes -oConnectTimeout=10'],
            'ssh command': [
                VDR.V_STRING, 'ssh -oBatchMode=yes -oConnectTimeout=10'],
            'use login shell': [VDR.V_BOOLEAN, True],
            'cylc executable': [VDR.V_STRING, 'cylc'],
            'global init-script': [VDR.V_STRING],
            'copyable environment variables': [VDR.V_STRING_LIST],
            'retrieve job logs': [VDR.V_BOOLEAN],
            'retrieve job logs command': [VDR.V_STRING, 'rsync -a'],
            'retrieve job logs max size': [VDR.V_STRING],
            'retrieve job logs retry delays': [VDR.V_INTERVAL_LIST],
            'task event handler retry delays': [VDR.V_INTERVAL_LIST],
            'tail command template': [
                VDR.V_STRING, 'tail -n +1 -F %(filename)s'],
            'batch systems': {
                '__MANY__': {
                    'err tailer': [VDR.V_STRING],
                    'out tailer': [VDR.V_STRING],
                    'err viewer': [VDR.V_STRING],
                    'out viewer': [VDR.V_STRING],
                    'job name length maximum': [VDR.V_INTEGER],
                    'execution time limit polling intervals': [
                        VDR.V_INTERVAL_LIST],
                },
            },
        },
        '__MANY__': {
            'run directory': [VDR.V_STRING],
            'work directory': [VDR.V_STRING],
            'task communication method': [
                VDR.V_STRING, 'default', 'ssh', 'poll'],
            'submission polling intervals': [VDR.V_INTERVAL_LIST],
            'execution polling intervals': [VDR.V_INTERVAL_LIST],
            'scp command': [VDR.V_STRING],
            'ssh command': [VDR.V_STRING],
            'use login shell': [VDR.V_BOOLEAN],
            'cylc executable': [VDR.V_STRING],
            'global init-script': [VDR.V_STRING],
            'copyable environment variables': [VDR.V_STRING_LIST],
            'retrieve job logs': [VDR.V_BOOLEAN],
            'retrieve job logs command': [VDR.V_STRING],
            'retrieve job logs max size': [VDR.V_STRING],
            'retrieve job logs retry delays': [VDR.V_INTERVAL_LIST],
            'task event handler retry delays': [VDR.V_INTERVAL_LIST],
            'tail command template': [VDR.V_STRING],
            'batch systems': {
                '__MANY__': {
                    'err tailer': [VDR.V_STRING],
                    'out tailer': [VDR.V_STRING],
                    'out viewer': [VDR.V_STRING],
                    'err viewer': [VDR.V_STRING],
                    'job name length maximum': [VDR.V_INTEGER],
                    'execution time limit polling intervals': [
                        VDR.V_INTERVAL_LIST],
                },
            },
        },
    },

    'task events': {
        'execution timeout': [VDR.V_INTERVAL],
        'handlers': [VDR.V_STRING_LIST],
        'handler events': [VDR.V_STRING_LIST],
        'handler retry delays': [VDR.V_INTERVAL_LIST, None],
        'mail events': [VDR.V_STRING_LIST],
        'mail from': [VDR.V_STRING],
        'mail retry delays': [VDR.V_INTERVAL_LIST],
        'mail smtp': [VDR.V_STRING],
        'mail to': [VDR.V_STRING],
        'submission timeout': [VDR.V_INTERVAL],
    },

    'test battery': {
        'remote host with shared fs': [VDR.V_STRING],
        'remote host': [VDR.V_STRING],
        'remote owner': [VDR.V_STRING],
        'batch systems': {
            '__MANY__': {
                'host': [VDR.V_STRING],
                'out viewer': [VDR.V_STRING],
                'err viewer': [VDR.V_STRING],
                'directives': {
                    '__MANY__': [VDR.V_STRING],
                },
            },
        },
    },

    'suite host self-identification': {
        'method': [VDR.V_STRING, 'name', 'address', 'hardwired'],
        'target': [VDR.V_STRING, 'google.com'],
        'host': [VDR.V_STRING],
    },

    'authentication': {
        # Allow owners to grant public shutdown rights at the most, not full
        # control.
        'public': (
            [VDR.V_STRING]
            + [level.name.lower().replace('_', '-') for level in [
                Priv.STATE_TOTALS, Priv.IDENTITY, Priv.DESCRIPTION,
                Priv.STATE_TOTALS, Priv.READ, Priv.SHUTDOWN]])
    },

    'suite servers': {
        'run hosts': [VDR.V_SPACELESS_STRING_LIST],
        'run ports': [VDR.V_INTEGER_LIST, list(range(43001, 43101))],
        'condemned hosts': [VDR.V_ABSOLUTE_HOST_LIST],
        'auto restart delay': [VDR.V_INTERVAL],
        'run host select': {
            'rank': [VDR.V_STRING, 'random', 'load:1', 'load:5', 'load:15',
                     'memory', 'disk-space'],
            'thresholds': [VDR.V_STRING],
        },
    },
}


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

    u.upgrade()


class GlobalConfig(ParsecConfig):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.

    For all derived items - paths hardwired under the configurable top
    levels - use the get_derived_host_item(suite,host) method.
    """

    _DEFAULT = None
    _HOME = os.getenv('HOME') or get_user_home()
    CONF_BASE = "global.rc"
    # Site global.rc loc preference: if not in etc/ look in old conf/.
    SITE_CONF_DIR = os.path.join(os.environ["CYLC_DIR"], "etc")
    SITE_CONF_DIR_OLD = os.path.join(os.environ["CYLC_DIR"], "conf")
    # User global.rc loc preference: if not in .cylc/x.y.z/ look in .cylc/.
    USER_CONF_DIR_1 = os.path.join(_HOME, '.cylc', CYLC_VERSION)
    USER_CONF_DIR_2 = os.path.join(_HOME, '.cylc')

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
        LOG.debug("Loading site/user global config files")
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str is None:
            # CYLC_CONF_PATH not defined, use default locations.
            for conf_dir_1, conf_dir_2, conf_type in [
                    (self.SITE_CONF_DIR, self.SITE_CONF_DIR_OLD,
                     upgrader.SITE_CONFIG),
                    (self.USER_CONF_DIR_1, self.USER_CONF_DIR_2,
                     upgrader.USER_CONFIG)]:
                fname1 = os.path.join(conf_dir_1, self.CONF_BASE)
                fname2 = os.path.join(conf_dir_2, self.CONF_BASE)
                if os.access(fname1, os.F_OK | os.R_OK):
                    fname = fname1
                elif os.access(fname2, os.F_OK | os.R_OK):
                    fname = fname2
                else:
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
                    break
        elif conf_path_str:
            # CYLC_CONF_PATH defined with a value
            for path in conf_path_str.split(os.pathsep):
                fname = os.path.join(path, self.CONF_BASE)
                if os.access(fname, os.F_OK | os.R_OK):
                    self.loadcfg(fname, upgrader.USER_CONFIG)
        # (OK if no global.rc is found, just use system defaults).
        self.transform()

    def get_derived_host_item(
            self, suite, item, host=None, owner=None, replace_home=False):
        """Compute hardwired paths relative to the configurable top dirs."""

        # suite run dir
        srdir = os.path.join(
            self.get_host_item('run directory', host, owner, replace_home),
            suite)
        # suite workspace
        swdir = os.path.join(
            self.get_host_item('work directory', host, owner, replace_home),
            suite)

        if item == 'suite run directory':
            value = srdir

        elif item == 'suite log directory':
            value = os.path.join(srdir, 'log', 'suite')

        elif item == 'suite log':
            value = os.path.join(srdir, 'log', 'suite', 'log')

        elif item == 'suite job log directory':
            value = os.path.join(srdir, 'log', 'job')

        elif item == 'suite config log directory':
            value = os.path.join(srdir, 'log', 'suiterc')

        elif item == 'suite work root':
            value = swdir

        elif item == 'suite work directory':
            value = os.path.join(swdir, 'work')

        elif item == 'suite share directory':
            value = os.path.join(swdir, 'share')

        else:
            raise GlobalConfigError("Illegal derived item: " + item)

        return value

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

    def roll_directory(self, dir_, name, archlen=0):
        """Create a directory after rolling back any previous instances of it.

        E.g. if archlen = 2 we keep:
            dir_, dir_.1, dir_.2. If 0 keep no old ones.
        """
        for i in range(archlen, -1, -1):  # archlen...0
            if i > 0:
                dpath = dir_ + '.' + str(i)
            else:
                dpath = dir_
            if os.path.exists(dpath):
                if i >= archlen:
                    # remove oldest backup
                    shutil.rmtree(dpath)
                else:
                    # roll others over
                    os.rename(dpath, dir_ + '.' + str(i + 1))
        self.create_directory(dir_, name)

    @staticmethod
    def create_directory(dir_, name):
        """Create directory. Raise GlobalConfigError on error."""
        try:
            os.makedirs(dir_, exist_ok=True)
        except OSError as exc:
            LOG.exception(exc)
            raise GlobalConfigError(
                'Failed to create directory "' + name + '"')

    def create_cylc_run_tree(self, suite):
        """Create all top-level cylc-run output dirs on the suite host."""
        cfg = self.get()
        item = 'suite run directory'
        idir = self.get_derived_host_item(suite, item)
        LOG.debug('creating %s: %s', item, idir)
        if cfg['enable run directory housekeeping']:
            self.roll_directory(
                idir, item, cfg['run directory rolling archive length'])

        for item in [
                'suite log directory',
                'suite job log directory',
                'suite config log directory',
                'suite work directory',
                'suite share directory']:
            idir = self.get_derived_host_item(suite, item)
            LOG.debug('creating %s: %s', item, idir)
            self.create_directory(idir, item)

        item = 'temporary directory'
        value = cfg[item]
        if value:
            self.create_directory(value, item)

    def get_tmpdir(self):
        """Make a new temporary directory and arrange for it to be
        deleted automatically when we're finished with it. Call this
        explicitly just before use to ensure the directory is not
        deleted by other processes before it is needed. THIS IS
        CURRENTLY ONLY USED BY A FEW CYLC COMMANDS. If cylc suites
        ever need it this must be called AFTER FORKING TO DAEMON MODE or
        atexit() will delete the directory when the initial process
        exits after forking."""

        cfg = self.get()
        tdir = cfg['temporary directory']
        if tdir:
            tdir = os.path.expandvars(tdir)
            tmpdir = mkdtemp(prefix="cylc-", dir=os.path.expandvars(tdir))
        else:
            tmpdir = mkdtemp(prefix="cylc-")
        # self-cleanup
        atexit.register(lambda: shutil.rmtree(tmpdir))
        # now replace the original item to allow direct access
        cfg['temporary directory'] = tmpdir
        return tmpdir

    def transform(self):
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
