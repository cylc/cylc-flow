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
"Cylc site and user configuration file spec."

import os
import sys
import re
import atexit
import shutil
from tempfile import mkdtemp
from parsec.config import config
from parsec.validate import validator as vdr
from parsec.validate import coercers
from parsec import ParsecError
from parsec.upgrade import upgrader, converter
from cylc.hostuserutil import is_remote_user
from cylc.envvar import expandvars
from cylc.mkdir_p import mkdir_p
import cylc.flags
from cylc.cfgspec.utils import (
    coerce_interval, coerce_interval_list, DurationFloat)
from cylc.network import PRIVILEGE_LEVELS, PRIV_STATE_TOTALS, PRIV_SHUTDOWN

coercers['interval'] = coerce_interval
coercers['interval_list'] = coerce_interval_list

SPEC = {
    'process pool size': vdr(vtype='integer', default=4),
    'temporary directory': vdr(vtype='string'),
    'state dump rolling archive length': vdr(
        vtype='integer', default=10),
    'disable interactive command prompts': vdr(vtype='boolean', default=True),
    'enable run directory housekeeping': vdr(vtype='boolean', default=False),
    'run directory rolling archive length': vdr(
        vtype='integer', default=2),
    'task host select command timeout': vdr(
        vtype='interval', default=DurationFloat(10)),
    'task messaging': {
        'retry interval': vdr(
            vtype='interval', default=DurationFloat(5)),
        'maximum number of tries': vdr(vtype='integer', default=7),
        'connection timeout': vdr(
            vtype='interval', default=DurationFloat(30)),
    },

    'cylc': {
        'UTC mode': vdr(vtype='boolean', default=False),
        'health check interval': vdr(
            vtype='interval', default=DurationFloat(600)),
        'task event mail interval': vdr(
            vtype='interval', default=DurationFloat(300)),
        'events': {
            'handlers': vdr(vtype='string_list', default=[]),
            'handler events': vdr(vtype='string_list', default=[]),
            'mail events': vdr(vtype='string_list', default=[]),
            'mail from': vdr(vtype='string'),
            'mail smtp': vdr(vtype='string'),
            'mail to': vdr(vtype='string'),
            'mail footer': vdr(vtype='string'),
            'startup handler': vdr(vtype='string_list', default=[]),
            'timeout handler': vdr(vtype='string_list', default=[]),
            'inactivity handler': vdr(vtype='string_list', default=[]),
            'shutdown handler': vdr(vtype='string_list', default=[]),
            'stalled handler': vdr(vtype='string_list', default=[]),
            'timeout': vdr(vtype='interval'),
            'inactivity': vdr(vtype='interval'),
            'abort on timeout': vdr(vtype='boolean', default=False),
            'abort on inactivity': vdr(vtype='boolean', default=False),
            'abort on stalled': vdr(vtype='boolean', default=False),
        },
    },

    'suite logging': {
        'roll over at start-up': vdr(vtype='boolean', default=True),
        'rolling archive length': vdr(vtype='integer', default=5),
        'maximum size in bytes': vdr(vtype='integer', default=1000000),
    },

    'documentation': {
        'files': {
            'html index': vdr(
                vtype='string', default="$CYLC_DIR/doc/install/index.html"),
            'pdf user guide': vdr(
                vtype='string',
                default="$CYLC_DIR/doc/install/cylc-user-guide.pdf"),
            'multi-page html user guide': vdr(
                vtype='string',
                default="$CYLC_DIR/doc/install/html/multi/cug-html.html"),
            'single-page html user guide': vdr(
                vtype='string',
                default="$CYLC_DIR/doc/install/html/single/cug-html.html"),
        },
        'urls': {
            'internet homepage': vdr(
                vtype='string', default="http://cylc.github.io/cylc/"),
            'local index': vdr(vtype='string', default=None),
        },
    },

    'document viewers': {
        'pdf': vdr(vtype='string', default="evince"),
        'html': vdr(vtype='string', default="firefox"),
    },
    'editors': {
        'terminal': vdr(vtype='string', default="vim"),
        'gui': vdr(vtype='string', default="gvim -f"),
    },

    'communication': {
        'method': vdr(vtype='string', default="https",
                      options=["https", "http"]),
        'base port': vdr(vtype='integer', default=43001),
        'maximum number of ports': vdr(vtype='integer', default=100),
        'proxies on': vdr(vtype='boolean', default=False),
        'options': vdr(vtype='string_list', default=[]),
    },

    'monitor': {
        'sort order': vdr(vtype='string',
                          options=["alphanumeric", "definition"],
                          default="definition"),
    },

    'hosts': {
        'localhost': {
            'run directory': vdr(vtype='string', default="$HOME/cylc-run"),
            'work directory': vdr(vtype='string', default="$HOME/cylc-run"),
            'task communication method': vdr(
                vtype='string',
                options=["default", "ssh", "poll"], default="default"),
            'submission polling intervals': vdr(
                vtype='interval_list', default=[]),
            'execution polling intervals': vdr(
                vtype='interval_list', default=[]),
            'scp command': vdr(
                vtype='string',
                default='scp -oBatchMode=yes -oConnectTimeout=10'),
            'ssh command': vdr(
                vtype='string',
                default='ssh -oBatchMode=yes -oConnectTimeout=10'),
            'use login shell': vdr(vtype='boolean', default=True),
            'cylc executable': vdr(vtype='string', default='cylc'),
            'global init-script': vdr(vtype='string', default=''),
            'copyable environment variables': vdr(
                vtype='string_list', default=[]),
            'retrieve job logs': vdr(vtype='boolean', default=False),
            'retrieve job logs command': vdr(
                vtype='string', default='rsync -a'),
            'retrieve job logs max size': vdr(vtype='string'),
            'retrieve job logs retry delays': vdr(
                vtype='interval_list', default=[]),
            'task event handler retry delays': vdr(
                vtype='interval_list', default=[]),
            'local tail command template': vdr(
                vtype='string', default="tail -n +1 -F %(filename)s"),
            'remote tail command template': vdr(
                vtype='string',
                default=(
                    "tail --pid=`ps h -o ppid $$" +
                    " | sed -e s/[[:space:]]//g` -n +1 -F %(filename)s")),
            # Template for tail commands on remote files.  On signal to "ssh"
            # client, a signal is sent to "sshd" on server.  However, "sshd"
            # cannot send a signal to the "tail" command, because it is not a
            # terminal. Apparently, we can use "ssh -t" or "ssh -tt", but that
            # just causes the command to hang here for some reason. The easiest
            # solution is to use the "--pid=PID" option of the "tail" command,
            # so it dies as soon as PID dies. Note: if remote login shell is
            # bash/ksh, we can use $PPID instead of `ps...` command, but we
            # have to support login shell "tcsh" too.
            'batch systems': {
                '__MANY__': {
                    'err tailer': vdr(vtype='string'),
                    'out tailer': vdr(vtype='string'),
                    'err viewer': vdr(vtype='string'),
                    'out viewer': vdr(vtype='string'),
                    'job name length maximum': vdr(vtype='integer'),
                    'execution time limit polling intervals': vdr(
                        vtype='interval_list', default=[]),
                },
            },
        },
        '__MANY__': {
            'run directory': vdr(vtype='string'),
            'work directory': vdr(vtype='string'),
            'task communication method': vdr(
                vtype='string', options=["default", "ssh", "poll"]),
            'submission polling intervals': vdr(
                vtype='interval_list', default=[]),
            'execution polling intervals': vdr(
                vtype='interval_list', default=[]),
            'scp command': vdr(vtype='string'),
            'ssh command': vdr(vtype='string'),
            'use login shell': vdr(vtype='boolean', default=None),
            'cylc executable': vdr(vtype='string'),
            'global init-script': vdr(vtype='string'),
            'copyable environment variables': vdr(
                vtype='string_list', default=[]),
            'retrieve job logs': vdr(vtype='boolean', default=None),
            'retrieve job logs command': vdr(vtype='string'),
            'retrieve job logs max size': vdr(vtype='string'),
            'retrieve job logs retry delays': vdr(
                vtype='interval_list'),
            'task event handler retry delays': vdr(
                vtype='interval_list'),
            'local tail command template': vdr(vtype='string'),
            'remote tail command template': vdr(vtype='string'),
            'batch systems': {
                '__MANY__': {
                    'err tailer': vdr(vtype='string'),
                    'out tailer': vdr(vtype='string'),
                    'out viewer': vdr(vtype='string'),
                    'err viewer': vdr(vtype='string'),
                    'job name length maximum': vdr(vtype='integer'),
                    'execution time limit polling intervals': vdr(
                        vtype='interval_list'),
                },
            },
        },
    },

    'task events': {
        'execution timeout': vdr(vtype='interval'),
        'handlers': vdr(vtype='string_list', default=[]),
        'handler events': vdr(vtype='string_list', default=[]),
        'handler retry delays': vdr(vtype='interval_list'),
        'mail events': vdr(vtype='string_list', default=[]),
        'mail from': vdr(vtype='string'),
        'mail retry delays': vdr(vtype='interval_list', default=[]),
        'mail smtp': vdr(vtype='string'),
        'mail to': vdr(vtype='string'),
        'reset timer': vdr(vtype='boolean', default=False),
        'submission timeout': vdr(vtype='interval'),
    },

    'test battery': {
        'remote host with shared fs': vdr(vtype='string'),
        'remote host': vdr(vtype='string'),
        'batch systems': {
            '__MANY__': {
                'host': vdr(vtype='string'),
                'out viewer': vdr(vtype='string'),
                'err viewer': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
        },
    },

    'suite host self-identification': {
        'method': vdr(
            vtype='string',
            options=["name", "address", "hardwired"],
            default="name"),
        'target': vdr(vtype='string', default="google.com"),
        'host': vdr(vtype='string'),
    },

    'suite host scanning': {
        'hosts': vdr(vtype='string_list', default=["localhost"])
    },

    'authentication': {
        # Allow owners to grant public shutdown rights at the most, not full
        # control.
        'public': vdr(
            vtype='string',
            options=(
                PRIVILEGE_LEVELS[:PRIVILEGE_LEVELS.index(PRIV_SHUTDOWN) + 1]),
            default=PRIV_STATE_TOTALS),
    },
}


def upg(cfg, descr):
    """Upgrader."""
    add_bin_dir = converter(lambda x: x + '/bin', "Added + '/bin' to path")
    use_ssh = converter(lambda x: "ssh", "set to 'ssh'")
    u = upgrader(cfg, descr)
    u.deprecate('5.1.1', ['editors', 'in-terminal'], ['editors', 'terminal'])
    u.deprecate('5.1.1', ['task hosts'], ['hosts'])
    u.deprecate('5.1.1', ['hosts', 'local'], ['hosts', 'localhost'])
    u.deprecate(
        '5.1.1',
        ['hosts', '__MANY__', 'workspace directory'],
        ['hosts', '__MANY__', 'workdirectory'])
    u.deprecate(
        '5.1.1',
        ['hosts', '__MANY__', 'cylc directory'],
        ['hosts', '__MANY__', 'cylc bin directory'],
        add_bin_dir)
    u.obsolete(
        '5.2.0',
        ['hosts', '__MANY__', 'cylc bin directory'],
        ['hosts', '__MANY__', 'cylc bin directory'])
    u.deprecate(
        '5.2.0',
        ['hosts', '__MANY__', 'use ssh messaging'],
        ['hosts', '__MANY__', 'task communication method'],
        use_ssh)
    u.deprecate(
        '6.1.2',
        ['task messaging', 'connection timeout in seconds'],
        ['task messaging', 'connection timeout'])
    u.deprecate(
        '6.1.2',
        ['task messaging', 'retry interval in seconds'],
        ['task messaging', 'retry interval'])
    u.deprecate(
        '6.4.0',
        ['runtime', '__MANY__', 'global initial scripting'],
        ['runtime', '__MANY__', 'global init-script'])
    for batch_sys_name in ['loadleveler', 'lsf', 'pbs', 'sge', 'slurm']:
        u.deprecate(
            '6.4.1',
            ['test battery', 'directives', batch_sys_name + ' host'],
            ['test battery', 'batch systems', batch_sys_name, 'host'])
        u.deprecate(
            '6.4.1',
            ['test battery', 'directives', batch_sys_name + ' directives'],
            ['test battery', 'batch systems', batch_sys_name, 'directives'])
    u.obsolete('6.4.1', ['test battery', 'directives'])
    u.obsolete('6.11.0', ['state dump rolling archive length'])
    u.deprecate('6.11.0', ['cylc', 'event hooks'], ['cylc', 'events'])
    for key in SPEC['cylc']['events']:
        u.deprecate(
            '6.11.0', ['cylc', 'event hooks', key], ['cylc', 'events', key])
    u.obsolete(
        '7.0.0',
        ['pyro', 'base port']
    )
    u.obsolete(
        '7.0.0',
        ['pyro', 'maximum number of ports'],
        ['communication', 'maximum number of ports']
    )
    u.obsolete(
        '7.0.0',
        ['pyro', 'ports directory'],
    )
    u.obsolete(
        '7.0.0',
        ['pyro']
    )
    u.obsolete(
        '7.0.0',
        ['authentication', 'hashes']
    )
    u.obsolete(
        '7.0.0',
        ['authentication', 'scan hash']
    )
    u.deprecate(
        '7.0.0',
        ['execution polling intervals'],
        ['hosts', 'localhost', 'execution polling intervals'])
    u.deprecate(
        '7.0.0',
        ['submission polling intervals'],
        ['hosts', 'localhost', 'submission polling intervals'])
    u.deprecate(
        '7.3.1',
        ['hosts', '__MANY__', 'remote shell template'],
        ['hosts', '__MANY__', 'ssh command'])
    u.deprecate(
        '7.3.1',
        ['hosts', '__MANY__', 'remote copy template'],
        ['hosts', '__MANY__', 'scp command'])
    u.upgrade()


class GlobalConfigError(Exception):
    """Error in global site/user configuration."""

    def __str__(self):
        return repr(self.args[0])


class GlobalConfig(config):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.

    For all derived items - paths hardwired under the configurable top
    levels - use the get_derived_host_item(suite,host) method.
    """

    _DEFAULT = None
    CONF_BASE = "global.rc"
    SITE_CONF_DIR = os.path.join(os.environ["CYLC_DIR"], "conf")
    USER_CONF_DIR = os.path.join(os.environ['HOME'], '.cylc')
    OLD_SITE_CONF_BASE = os.path.join("siterc", "site.rc")
    OLD_USER_CONF_BASE = os.path.join("user.rc")

    @classmethod
    def get_inst(cls):
        """Return the singleton instance."""
        if not cls._DEFAULT:
            cls._DEFAULT = cls(SPEC, upg)
            cls._DEFAULT.load()
        return cls._DEFAULT

    def load(self):
        """Load or reload configuration from files."""
        self.sparse.clear()
        self.dense.clear()
        if cylc.flags.verbose:
            print "Loading site/user config files"
        conf_path_str = os.getenv("CYLC_CONF_PATH")
        if conf_path_str is None:
            # CYLC_CONF_PATH not defined, use default locations
            for old_base, conf_dir, is_site in [
                    [self.OLD_SITE_CONF_BASE, self.SITE_CONF_DIR, True],
                    [self.OLD_USER_CONF_BASE, self.USER_CONF_DIR, False]]:
                for base in [self.CONF_BASE, old_base]:
                    fname = os.path.join(conf_dir, base)
                    if os.access(fname, os.F_OK | os.R_OK):
                        try:
                            self.loadcfg(fname, "global config")
                        except ParsecError as exc:
                            if is_site:
                                sys.stderr.write(
                                    "WARNING: ignoring bad site config %s:"
                                    "\n%s\n" % (fname, str(exc)))
                            else:
                                sys.stderr.write(
                                    "ERROR: bad user config %s:\n" % (fname))
                                raise
                        break
        elif conf_path_str:
            # CYLC_CONF_PATH defined with a value
            for path in conf_path_str.split(os.pathsep):
                fname = os.path.join(path, self.CONF_BASE)
                if os.access(fname, os.F_OK | os.R_OK):
                    self.loadcfg(fname, "global config")
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
        if host:
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
                value = value.replace(os.environ['HOME'], '$HOME')
            elif is_remote_user(owner):
                # Replace with ~owner for direct access via local filesys
                # (works for standard cylc-run directory location).
                if owner_home is None:
                    owner_home = os.path.expanduser('~%s' % owner)
                value = value.replace(os.environ['HOME'], owner_home)
        if item == "task communication method" and value == "default":
            # Translate "default" to client-server comms: "https" or "http".
            value = cfg['communication']['method']
        return value

    def roll_directory(self, dir_, name, archlen=0):
        """Create a directory after rolling back any previous instances of it.

        E.g. if archlen = 2 we keep:
            dir_, dir_.1, dir_.2. If 0 keep no old ones.
        """
        for n in range(archlen, -1, -1):  # archlen...0
            if n > 0:
                dpath = dir_ + '.' + str(n)
            else:
                dpath = dir_
            if os.path.exists(dpath):
                if n >= archlen:
                    # remove oldest backup
                    shutil.rmtree(dpath)
                else:
                    # roll others over
                    os.rename(dpath, dir_ + '.' + str(n + 1))
        self.create_directory(dir_, name)

    @staticmethod
    def create_directory(dir_, name):
        """Create directory. Raise GlobalConfigError on error."""
        try:
            mkdir_p(dir_)
        except OSError as exc:
            print >> sys.stderr, str(exc)
            raise GlobalConfigError(
                'Failed to create directory "' + name + '"')

    def create_cylc_run_tree(self, suite):
        """Create all top-level cylc-run output dirs on the suite host."""

        if cylc.flags.verbose:
            print 'Creating the suite output tree:'

        cfg = self.get()

        item = 'suite run directory'
        if cylc.flags.verbose:
            print ' +', item
        idir = self.get_derived_host_item(suite, item)
        if cfg['enable run directory housekeeping']:
            self.roll_directory(
                idir, item, cfg['run directory rolling archive length'])

        for item in [
                'suite log directory',
                'suite job log directory',
                'suite config log directory',
                'suite work directory',
                'suite share directory']:
            if cylc.flags.verbose:
                print ' +', item
            idir = self.get_derived_host_item(suite, item)
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
            tdir = expandvars(tdir)
            tmpdir = mkdtemp(prefix="cylc-", dir=expandvars(tdir))
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
                    newvalue = newvalue.replace(os.environ['HOME'], '$HOME')
                cfg['hosts'][host][item] = newvalue

        # Expand environment variables and ~user in LOCAL file paths.
        for key, val in cfg['documentation']['files'].items():
            cfg['documentation']['files'][key] = expandvars(val)

        for key, val in cfg['hosts']['localhost'].items():
            if val and 'directory' in key:
                cfg['hosts']['localhost'][key] = expandvars(val)
