#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
"""Check that single-line config print works"""

import os
import sys

fpath = os.path.dirname(os.path.abspath(__file__))
# parsec
sys.path.append(fpath + '/../../..')


from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.validate import ParsecValidator as VDR

SPEC = {'foo': {'bar': {'__MANY__': [VDR.V_STRING]}}}
cfg = ParsecConfig(SPEC)
cfg.loadcfg("test.rc")

cfg.mdump(
    [['foo', 'bar', 'baz'], ['foo', 'bar', 'qux']], oneline=True, sparse=True)
