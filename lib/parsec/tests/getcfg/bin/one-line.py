#!/usr/bin/env python2
"""Check that single-line config print works"""

import os
import sys

fpath = os.path.dirname(os.path.abspath(__file__))
# parsec
sys.path.append(fpath + '/../../..')


from parsec.config import ParsecConfig
from parsec.validate import ParsecValidator as VDR

SPEC = {'foo': {'bar': {'__MANY__': [VDR.V_STRING]}}}
cfg = ParsecConfig(SPEC)
cfg.loadcfg("test.rc")

cfg.mdump(
    [['foo','bar','baz'], ['foo','bar','qux']], oneline=True, sparse=True)
