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

import os
import sys

fpath = os.path.dirname(os.path.abspath(__file__))

# spec
sys.path.append(fpath + '/../lib/python')
# parsec
sys.path.append(fpath + '/../../..')

from cfgspec import SPEC
from config import ParsecConfig

rcname = sys.argv[1]
rcfile = rcname + '.rc'

cfg = ParsecConfig(SPEC)

cfg.loadcfg(rcfile)

res = cfg.get(sparse=True)

for expected in res[rcname].keys():

    vals = cfg.get([rcname, expected], sparse=True).values()
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
        print >> sys.stderr, vals, ' is not all ', expected
        sys.exit("FAIL")
    else:
        print "OK"
