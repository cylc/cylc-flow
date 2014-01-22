#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import os,sys

if __name__ == "__main__":
    sys.path.append( os.path.join( os.path.dirname(os.path.abspath(__file__)), '..' ))

from fileparse import parse
from util import printcfg
from validate import validator as vdr
from validate import validate, expand

"""
Legal items and validators for the parsec test config file.
"""

TEST_FILE = os.path.join( os.path.dirname( os.path.abspath( __file__ )), 'test.rc' )

cfg = None

SPEC = {
        'unquoted' : vdr( vtype="string" ),
        'continuation' : vdr( vtype="string" ),
        'level 1' : 
        {
            'single-quoted' : vdr( vtype="string" ),
            'level 2' :
            {
                'double-quoted' : vdr( vtype="string" ),
                'level 3' :
                {
                    'single-line triple-single-quoted' : vdr( vtype="string" ),
                    'single-line triple-double-quoted' : vdr( vtype="string" ),
                    'empty value' : vdr( vtype="string" ),
                    },
                },
            'level 2_2' :
            {
                'multiline value' : vdr( vtype="string" ),
                '__MANY__' : vdr( vtype = "string" ),
                },
            },
        'level 1_1' :
        {
            'unquoted list' : vdr( vtype="string" ),
            'single-quoted list' : vdr( vtype="string" ),
            'double-quoted list' : vdr( vtype="string" ),
            },
        'validation' :
        {
            'integer value' : vdr( vtype="integer" ),
            'float value' : vdr( vtype="float" ),
            'boolean value' : vdr( vtype="boolean" ),
            'another boolean value' : vdr( vtype="boolean" ),
            'integer list' : vdr( vtype="integer_list" ),
            'float list' : vdr( vtype="float_list" ),
            'multiplier float list' : vdr( vtype="m_float_list" ),
            },
        }

def get_cfg( cfile=TEST_FILE, template_vars=[], template_vars_file=None ):
    global cfg
    if not cfg:
        cfg = parse( cfile,
                template_vars=template_vars,
                template_vars_file=template_vars_file )
        validate( cfg, SPEC )
        cfg = expand( cfg, SPEC )
    return cfg

def print_cfg():
    printcfg(get_cfg())

if __name__ == '__main__':
    try:
        print_cfg()
    except Exception, x:
        if '--debug' in sys.argv:
            raise
        print >> sys.stderr, x

