#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
