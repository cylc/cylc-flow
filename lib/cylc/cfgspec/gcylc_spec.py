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
from parsec.loadcfg import load_combined
from parsec.validate import validator as vdr
from parsec.util import printcfg

"""
Define items and validators for gcylc config files,
"""

SITE_FILE = os.path.join( os.environ['CYLC_DIR'], 'conf', 'gcylcrc', 'themes.rc' )
USER_FILE = os.path.join( os.environ['HOME'], '.cylc', 'gcylc.rc' )

cfg = None

SPEC = {
    'initial views' : vdr( vtype='string_list', default=["text","dot"] ),
    'ungrouped views' : vdr( vtype='string_list', default=[] ),
    'use theme'     : vdr( vtype='string', default="default" ),
    'themes' : {
        '__MANY__' : {
            'inherit'       : vdr( vtype='string', default="default" ),
            'defaults'      : vdr( vtype='string_list' ),
            'waiting'       : vdr( vtype='string_list' ),
            'runahead'      : vdr( vtype='string_list' ),
            'held'          : vdr( vtype='string_list' ),
            'queued'        : vdr( vtype='string_list' ),
            'submitting'    : vdr( vtype='string_list' ),
            'submitted'     : vdr( vtype='string_list' ),
            'submit-failed' : vdr( vtype='string_list' ),
            'running'       : vdr( vtype='string_list' ),
            'succeeded'     : vdr( vtype='string_list' ),
            'failed'        : vdr( vtype='string_list' ),
            'retrying'      : vdr( vtype='string_list' ),
            'submit-retrying' : vdr( vtype='string_list' ),
            },
        },
    }

def get_cfg( verbose=False ):
    global cfg
    if not cfg:
        cfg = load_combined( SITE_FILE, "site config",
                             USER_FILE, "user config",
                             SPEC, None, True, verbose )
    return cfg

def print_cfg():
    printcfg(get_cfg())

