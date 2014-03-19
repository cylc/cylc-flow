#!/usr/bin/env python

import os, sys

fpath = os.path.dirname(os.path.abspath(__file__))
# parsec
sys.path.append( fpath + '/../../..' )

"""
A missing config file should successfully yield an empty sparse config dict.
""" 

from config import config
from validate import validator as vdr
from OrderedDict import OrderedDict

SPEC = { 'title' : vdr( vtype="string" ) }
cfg = config( SPEC )
cfg.loadcfg( "missing.rc" )

if cfg.get(sparse=True) != OrderedDict():
    sys.exit(1)

