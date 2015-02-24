#!/usr/bin/env python

import os, sys

fpath = os.path.dirname(os.path.abspath(__file__))
# parsec
sys.path.append( fpath + '/../../..' )

"""
Check that single-line config print works
""" 

from parsec.config import config
from parsec.validate import validator as vdr
from parsec.OrderedDict import OrderedDict

SPEC = { 'foo' : { 'bar' : { '__MANY__' : vdr( vtype="string" ) } } }
cfg = config( SPEC )
cfg.loadcfg( "test.rc" )

cfg.mdump ( [['foo','bar','baz'],['foo','bar','qux']], oneline=True, sparse=True)
