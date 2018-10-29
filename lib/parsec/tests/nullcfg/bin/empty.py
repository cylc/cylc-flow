#!/usr/bin/env python2
"""
An empty config file should successfully yield an empty sparse config dict.
"""


import os, sys

fpath = os.path.dirname(os.path.abspath(__file__))
# parsec
sys.path.append(fpath + '/../../..')


from parsec.config import ParsecConfig
from parsec.validate import ParsecValidator as VDR
from parsec.OrderedDict import OrderedDict

SPEC = {'meta': {'title': [VDR.V_STRING]}}
cfg = ParsecConfig(SPEC)
cfg.loadcfg("empty.rc")

if cfg.get(sparse=True) != OrderedDict():
    sys.exit(1)
