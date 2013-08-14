#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from parsec.validate import validator as vdr
from parsec.upgrade import upgrader, converter
from parsec.loadcfg import load_combined
from parsec.util import printcfg

"""
Define items and validators for cylc site and user config files.
""" 

SITE_FILE = os.path.join( os.environ['CYLC_DIR'], 'conf', 'siterc', 'site.rc' )
USER_FILE = os.path.join( os.environ['HOME'], '.cylc', 'user.rc' )

cfg = None

SPEC = {
    'temporary directory'                 : vdr( vtype='string' ),
    'state dump rolling archive length'   : vdr( vtype='integer', vmin=1, default=10 ),
    'disable interactive command prompts' : vdr( vtype='boolean', default=True ),
    'enable run directory housekeeping'   : vdr( vtype='boolean', default=False ),
    'run directory rolling archive length': vdr( vtype='integer', vmin=0, default=2 ),
    'submission polling intervals'        : vdr( vtype='m_float_list', allow_zeroes=False, default=[1.0]), 
    'execution polling intervals'         : vdr( vtype='m_float_list', allow_zeroes=False, default=[1.0]),

    'task messaging' : {
        'retry interval in seconds'       : vdr( vtype='float', vmin=1, default=5 ),
        'maximum number of tries'         : vdr( vtype='integer', vmin=1, default=7 ),
        'connection timeout in seconds'   : vdr( vtype='float', vmin=1, default=30 ),
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
            'remote shell template'       : vdr( vtype='string', default='ssh -oBatchMode=yes %s' ),
            'use login shell'             : vdr( vtype='boolean', default=True ),
            },
        '__MANY__' : {
            'run directory'               : vdr( vtype='string', default=None ),
            'work directory'              : vdr( vtype='string', default=None),
            'task communication method'   : vdr( vtype='string', options=["pyro","ssh","poll"] ),
            'remote shell template'       : vdr( vtype='string' ),
            'use login shell'             : vdr( vtype='boolean', default=True ),
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

def upg( cfg, descr, verbose ):
    add_bin_dir = converter( lambda x: x + '/bin', "Added + '/bin' to path" )
    use_ssh = converter( lambda x: "ssh", "set to 'ssh'" )
    u = upgrader(cfg, SPEC, descr, verbose )
    u.deprecate( '5.1.1', ['editors','in-terminal'], ['editors','terminal'] )
    u.deprecate( '5.1.1', ['task hosts'], ['hosts'] )
    u.deprecate( '5.1.1', ['hosts','local'], ['hosts','localhost'] )
    u.deprecate( '5.1.1', ['hosts','__MANY__', 'workspace directory'], ['hosts','__MANY__', 'workdirectory'] )
    u.deprecate( '5.1.1', ['hosts','__MANY__', 'cylc directory'], ['hosts','__MANY__', 'cylc bin directory'], add_bin_dir )
    u.obsolete(  '5.2.0', ['hosts','__MANY__', 'cylc bin directory'], ['hosts','__MANY__', 'cylc bin directory'] )
    u.deprecate( '5.2.0', ['hosts','__MANY__', 'use ssh messaging'], ['hosts','__MANY__', 'task communication method'], use_ssh )
    u.upgrade()

def get_cfg( verbose=False ):
    global cfg
    if not cfg:
        cfg = load_combined( SITE_FILE, "site config",
                             USER_FILE, "user config",
                             SPEC, upg, True, verbose )
    return cfg

def print_cfg():
    printcfg(get_cfg())

