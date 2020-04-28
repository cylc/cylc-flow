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

import sys

from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.validate import ParsecValidator as VDR

SPEC = {
    'boolean': {'__MANY__': {'__MANY__': [VDR.V_BOOLEAN]}},
    'integer': {'__MANY__': {'__MANY__': [VDR.V_INTEGER]}},
    'float': {'__MANY__': {'__MANY__': [VDR.V_FLOAT]}},
    'string': {'__MANY__': {'__MANY__': [VDR.V_STRING]}},
    'string_list': {'__MANY__': {'__MANY__': [VDR.V_STRING_LIST]}},
    'spaceless_string_list': {'__MANY__': {'__MANY__': [
        VDR.V_SPACELESS_STRING_LIST]}},
    'float_list': {'__MANY__': {'__MANY__': [VDR.V_FLOAT_LIST]}},
    'integer_list': {'__MANY__': {'__MANY__': [VDR.V_INTEGER_LIST]}},
}


rcname = sys.argv[1]
rcfile = rcname + '.rc'

cfg = ParsecConfig(SPEC)

cfg.loadcfg(rcfile)

res = cfg.get(sparse=True)

for expected in res[rcname]:

    vals = list(cfg.get([rcname, expected], sparse=True).values())
    expected = expected.replace('COMMA', ',').replace('NULL', '')

    if rcname == 'boolean':
        expected = (expected == 'True') or False

    elif rcname == 'integer':
        expected = int(expected)

    elif rcname == 'float':
        expected = float(expected)

    elif rcname == 'integer_list':
        expected = [int(i) for i in expected.split('_')]

    elif rcname == 'float_list':
        expected = [float(i) for i in expected.split('_')]

    elif rcname in ['string_list', 'spaceless_string_list']:
        if expected:
            expected = expected.split('_')
        else:
            expected = []

    if vals.count(expected) != len(vals):
        print(vals, ' is not all ', expected, file=sys.stderr)
        sys.exit("FAIL")
    else:
        print("OK")
