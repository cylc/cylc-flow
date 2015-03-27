#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import os, sys, re
import atexit
import shutil
from tempfile import mkdtemp
from parsec.config import config
from parsec.validate import validator as vdr
from parsec.validate import (
    coercers, _strip_and_unquote, _strip_and_unquote_list, _expand_list,
    IllegalValueError
)
from parsec.util import itemstr
from parsec.upgrade import upgrader, converter
from parsec.fileparse import parse
from isodatetime.data import Calendar
from cylc.owner import user
from cylc.envvar import expandvars
from cylc.mkdir_p import mkdir_p
import cylc.flags
from cylc.cfgspec.suite import coerce_interval
from cylc.cfgspec.suite import coerce_interval_list


"Cylc site and user configuration file spec."

coercers['interval_seconds'] = (
    lambda *args: coerce_interval(*args, check_syntax_version=False))
coercers['interval_minutes_list'] = (
    lambda *args: coerce_interval_list(*args, back_comp_unit_factor=60,
                                       check_syntax_version=False))

SPEC = {
    'process pool size'                   : vdr( vtype='integer', default=None ),
    'temporary directory'                 : vdr( vtype='string' ),
    'state dump rolling archive length'   : vdr( vtype='integer', vmin=1, default=10 ),
    'disable interactive command prompts' : vdr( vtype='boolean', default=True ),
    'enable run directory housekeeping'   : vdr( vtype='boolean', default=False ),
    'run directory rolling archive length': vdr( vtype='integer', vmin=0, default=2 ),
    'submission polling intervals'        : vdr( vtype='interval_minutes_list', default=[]),
    'execution polling intervals'         : vdr( vtype='interval_minutes_list', default=[]),

    'task host select command timeout'    : vdr( vtype='interval_seconds', default=10),
    'task messaging' : {
        'retry interval'                  : vdr( vtype='interval_seconds', default=5),
        'maximum number of tries'         : vdr( vtype='integer', vmin=1, default=7 ),
        'connection timeout'              : vdr( vtype='interval_seconds', default=30),

        },

    'suite logging' : {
        'roll over at start-up'           : vdr( vtype='boolean', default=True ),
        'rolling archive length'          : vdr( vtype='integer', vmin=1, default=5 ),
        'maximum size in bytes'           : vdr( vtype='integer', vmin=1000, default=1000000 ),
        },

    'documentation' : {
        'files' : {
            'html index'                  : vdr( vtype='string', default="$CYLC_DIR/doc/index.html" ),
            'pdf user guide'              : vdr( vtype='string', default="$CYLC_DIR/doc/pdf/cug-pdf.pdf" ),
            'multi-page html user guide'  : vdr( vtype='string', default="$CYLC_DIR/doc/html/multi/cug-html.html" ),
            'single-page html user guide' : vdr( vtype='string', default="$CYLC_DIR/doc/html/single/cug-html.html" ),
            },
        'urls' : {
            'internet homepage'           : vdr( vtype='string', default="http://cylc.github.com/cylc/" ),
            'local index'                 : vdr( vtype='string', default=None ),
            },
        },

    'document viewers' : {
        'pdf'                             : vdr( vtype='string', default="evince" ),
        'html'                            : vdr( vtype='string', default="firefox" ),
        },
    'editors' : {
        'terminal'                        : vdr( vtype='string', default="vim" ),
        'gui'                             : vdr( vtype='string', default="gvim -f" ),
        },

    'pyro' : {
        'base port'                       : vdr( vtype='integer', default=7766 ),
        'maximum number of ports'         : vdr( vtype='integer', default=100 ),
        'ports directory'                 : vdr( vtype='string', default="$HOME/.cylc/ports/" ),
        },

    'hosts' : {
        'localhost' : {
            'run directory'               : vdr( vtype='string', default="$HOME/cylc-run" ),
            'work directory'              : vdr( vtype='string', default="$HOME/cylc-run" ),
            'task communication method'   : vdr( vtype='string', options=[ "pyro", "ssh", "poll"], default="pyro" ),
            'remote copy template'        : vdr( vtype='string', default='scp -oBatchMode=yes -oConnectTimeout=10' ),
            'remote shell template'       : vdr( vtype='string', default='ssh -oBatchMode=yes -oConnectTimeout=10' ),
            'use login shell'             : vdr( vtype='boolean', default=True ),
            'cylc executable'             : vdr( vtype='string', default='cylc'  ),
            'global initial scripting'    : vdr( vtype='string', default='' ),
            'copyable environment variables': vdr(vtype='string_list', default=[]),
            },
        '__MANY__' : {
            'run directory'               : vdr( vtype='string'  ),
            'work directory'              : vdr( vtype='string'  ),
            'task communication method'   : vdr( vtype='string', options=[ "pyro", "ssh", "poll"] ),
            'remote copy template'        : vdr( vtype='string'  ),
            'remote shell template'       : vdr( vtype='string'  ),
            'use login shell'             : vdr( vtype='boolean' ),
            'cylc executable'             : vdr( vtype='string'  ),
            'global initial scripting'    : vdr( vtype='string'  ),
            'copyable environment variables': vdr(vtype='string_list', default=[]),
            },
        },

    'test battery': {
        'remote host with shared fs': vdr(vtype='string'),
        'remote host': vdr(vtype='string'),
        'batch systems': {
            'loadleveler': {
                'host': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
            'lsf': {
                'host': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
            'pbs': {
                'host': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
            'sge': {
                'host': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
            'slurm': {
                'host': vdr(vtype='string'),
                'directives': {'__MANY__': vdr(vtype='string')},
            },
        },
    },

    'suite host self-identification' : {
        'method'                          : vdr( vtype='string', options=["name","address","hardwired"], default="name" ),
        'target'                          : vdr( vtype='string', default="google.com" ),
        'host'                            : vdr( vtype='string' ),
        },

    'suite host scanning' : {
        'hosts'                           : vdr( vtype='string_list', default=["localhost"]),
        }
    }


def upg( cfg, descr ):
    add_bin_dir = converter( lambda x: x + '/bin', "Added + '/bin' to path" )
    use_ssh = converter( lambda x: "ssh", "set to 'ssh'" )
    u = upgrader(cfg, descr )
    u.deprecate( '5.1.1', ['editors','in-terminal'], ['editors','terminal'] )
    u.deprecate( '5.1.1', ['task hosts'], ['hosts'] )
    u.deprecate( '5.1.1', ['hosts','local'], ['hosts','localhost'] )
    u.deprecate( '5.1.1', ['hosts','__MANY__', 'workspace directory'], ['hosts','__MANY__', 'workdirectory'] )
    u.deprecate( '5.1.1', ['hosts','__MANY__', 'cylc directory'], ['hosts','__MANY__', 'cylc bin directory'], add_bin_dir )
    u.obsolete(  '5.2.0', ['hosts','__MANY__', 'cylc bin directory'], ['hosts','__MANY__', 'cylc bin directory'] )
    u.deprecate( '5.2.0', ['hosts','__MANY__', 'use ssh messaging'], ['hosts','__MANY__', 'task communication method'], use_ssh )
    u.upgrade()
    u.deprecate( '6.1.2', ['task messaging', 'connection timeout in seconds'], ['task messaging', 'connection timeout'] )
    u.deprecate( '6.1.2', ['task messaging', 'retry interval in seconds'], ['task messaging', 'retry interval'] )
    for batch_sys_name in ['loadleveler', 'lsf', 'pbs', 'sge', 'slurm']:
        u.deprecate('6.4.1',
            ['test battery', 'directives', batch_sys_name + ' host'],
            ['test battery', 'batch systems', batch_sys_name, 'host'])
        u.deprecate('6.4.1',
            ['test battery', 'directives', batch_sys_name + ' directives',
             '__MANY__'],
            ['test battery', 'batch systems', batch_sys_name, 'directives',
             '__MANY__'])

class GlobalConfigError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class GlobalConfig( config ):
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
    def default(cls):
        """Return the singleton instance."""
        if not cls._DEFAULT:
            if cylc.flags.verbose:
                print "Loading site/user config files"
            cls._DEFAULT = cls(SPEC, upg)
            conf_path_str = os.getenv("CYLC_CONF_PATH")
            if conf_path_str is None:
                # CYLC_CONF_PATH not defined, use default locations
                for old_base, conf_dir in [
                        [cls.OLD_SITE_CONF_BASE, cls.SITE_CONF_DIR],
                        [cls.OLD_USER_CONF_BASE, cls.USER_CONF_DIR]]:
                    for base in [cls.CONF_BASE, old_base]:
                        file_name = os.path.join(conf_dir, base)
                        if os.access(file_name, os.F_OK | os.R_OK):
                            cls._DEFAULT.loadcfg(
                                file_name, "global config", silent=True)
                            break
            elif conf_path_str:
                # CYLC_CONF_PATH defined with a value
                for path in conf_path_str.split(os.pathsep):
                    file_name = os.path.join(path, cls.CONF_BASE)
                    if os.access(file_name, os.F_OK | os.R_OK):
                        cls._DEFAULT.loadcfg(
                            file_name, "global config", silent=True)
            cls._DEFAULT.transform()
        return cls._DEFAULT
        

    def get_derived_host_item( self, suite, item, host=None, owner=None, replace=False ):
        """Compute hardwired paths relative to the configurable top dirs."""

        # suite run dir
        srdir = os.path.join( self.get_host_item( 'run directory',  host, owner, replace ), suite )
        # suite workspace
        swdir = os.path.join( self.get_host_item( 'work directory', host, owner, replace ), suite )

        if item == 'suite run directory':
            value = srdir

        elif item == 'suite log directory':
            value = os.path.join( srdir, 'log', 'suite' )

        elif item == 'suite job log directory':
            value = os.path.join( srdir, 'log', 'job' )

        elif item == 'suite config log directory':
            value = os.path.join( srdir, 'log', 'suiterc' )

        elif item == 'suite state directory':
            value = os.path.join( srdir, 'state' )

        elif item == 'suite work directory':
            value = os.path.join( swdir, 'work' )

        elif item == 'suite share directory':
            value = os.path.join( swdir, 'share' )

        else:
            raise GlobalConfigError( "Illegal derived item: " + item )

        return value

    def get_host_item( self, item, host=None, owner=None, replace=False ):
        """This allows hosts with no matching entry in the config file
        to default to appropriately modified localhost settings."""

        cfg = self.get()

        # (this may be called with explicit None values for localhost
        # and owner, so we can't use proper defaults in the arg list)
        if not host:
            # if no host is given the caller is asking about localhost
            host = 'localhost'
        if not owner:
            owner = user

        # is there a matching host section?
        host_key = None
        if host:
            if host in cfg['hosts']:
                # there's an entry for this host
                host_key = host
            else:
                # try for a pattern match
                for h in cfg['hosts']:
                    if re.match( h, host ):
                        host_key = h
                        break
        modify_dirs = False
        if host_key:
            # entry exists, any unset items under it have already
            # defaulted to modified localhost values (see site cfgspec)
            value = cfg['hosts'][host_key][item]
        else:
            # no entry so default to localhost and modify appropriately
            value = cfg['hosts']['localhost'][item]
            modify_dirs = True

        if value and ( 'directory' in item ) and ( modify_dirs or owner != user or replace ):
            # replace local home dir with $HOME for evaluation on other host
            value = value.replace( os.environ['HOME'], '$HOME' )

        return value

    def roll_directory( self, d, name, archlen=0 ):
        """
        Create a directory after rolling back any previous instances of it.
        e.g. if archlen = 2 we keep: d, d.1, d.2. If 0 keep no old ones.
        """
        for n in range( archlen, -1, -1 ): # archlen...0
            if n > 0:
                dpath = d+'.'+str(n)
            else:
                dpath = d
            if os.path.exists( dpath ):
                if n >= archlen:
                    # remove oldest backup
                    shutil.rmtree( dpath )
                else:
                    # roll others over
                    os.rename( dpath, d + '.' + str(n+1) )
        self.create_directory( d, name )

    def create_directory( self, d, name ):
        try:
            mkdir_p( d )
        except Exception, x:
            print >> sys.stderr, str(x)
            raise GlobalConfigError( 'Failed to create directory "' + name + '"' )

    def create_cylc_run_tree( self, suite ):
        """Create all top-level cylc-run output directories on the suite host."""

        if cylc.flags.verbose:
            print 'Creating the suite output tree:'

        cfg = self.get()

        item = 'suite run directory'
        if cylc.flags.verbose:
            print ' +', item
        idir = self.get_derived_host_item( suite, item )
        if cfg['enable run directory housekeeping']:
            self.roll_directory( idir, item, cfg['run directory rolling archive length'] )

        for item in [
                'suite log directory',
                'suite job log directory',
                'suite config log directory',
                'suite state directory',
                'suite work directory',
                'suite share directory']:
            if cylc.flags.verbose:
                print ' +', item
            idir = self.get_derived_host_item( suite, item )
            self.create_directory( idir, item )

        item = 'temporary directory'
        value = cfg[item]
        if value:
            self.create_directory( value, item )

        item = '[pyro]ports directory'
        value = cfg['pyro']['ports directory']
        self.create_directory( value, item )

    def get_tmpdir( self ):
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
            tdir = expandvars( tdir )
            tmpdir = mkdtemp(prefix="cylc-", dir=expandvars(tdir) )
        else:
            tmpdir = mkdtemp(prefix="cylc-")
        # self-cleanup
        atexit.register(lambda: shutil.rmtree(tmpdir))
        # now replace the original item to allow direct access
        cfg['temporary directory'] = tmpdir
        return tmpdir

    def transform( self ):
        # host item values of None default to modified localhost values
        cfg = self.get()

        for host in cfg['hosts']:
            if host == 'localhost':
                continue
            for item, value in cfg['hosts'][host].items():
                newvalue = value or cfg['hosts']['localhost'][item]
                if newvalue and 'directory' in item:
                    # replace local home dir with $HOME for evaluation on other host
                    newvalue = newvalue.replace( os.environ['HOME'], '$HOME' )
                cfg['hosts'][host][item] = newvalue

        # Expand environment variables and ~user in LOCAL file paths.
        for key,val in cfg['documentation']['files'].items():
            cfg['documentation']['files'][key] = expandvars( val )

        cfg['pyro']['ports directory'] = expandvars( cfg['pyro']['ports directory'] )

        for key,val in cfg['hosts']['localhost'].items():
            if val and 'directory' in key:
                cfg['hosts']['localhost'][key] = expandvars( val )


GLOBAL_CFG = GlobalConfig.default()
