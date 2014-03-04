#!/usr/bin/env python

import os, sys, re

fpath = os.path.dirname(os.path.abspath(__file__))

# spec
sys.path.append( fpath + '/../lib/python' )
# parsec
sys.path.append( fpath + '/../../..' )
# cylc (cycletime imported in validate.py!)
sys.path.append( fpath + '/../../../..' )

from cfgspec import SPEC
from config import config

rcname = sys.argv[1]
rcfile = rcname + '.rc'

cfg = config( SPEC )

cfg.loadcfg( rcfile, strict=True )

res = cfg.get( sparse=True)

for expected in res[rcname].keys():

    vals = cfg.get( [rcname, expected], sparse=True ).values()
    expected = re.sub( 'COMMA', ',', expected )

    if rcname == 'boolean':
        expected = ( expected == 'True' ) or False

    elif rcname == 'integer':
        expected = int( expected )

    elif rcname == 'float':
        expected = float( expected )

    elif rcname == 'integer_list':
        expected = [int(i) for i in expected.split('_')]

    elif rcname == 'float_list':
        expected = [float(i) for i in expected.split('_')]

    elif rcname == 'string_list':
        expected = expected.split('_')

    if vals.count(expected) != len( vals ):
        print >> sys.stderr, vals, ' is not all ', expected
        sys.exit( "FAIL" )
    else:
        print "OK"

