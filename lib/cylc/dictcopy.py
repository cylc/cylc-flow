#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

from OrderedDict import OrderedDict
from copy import copy

# Note that I've tried increasing the efficiency of replicate() and
# override() by inlining the recursive call or using dict.update(),
# knowing that [runtime] dicts are only two deep, but it seems to make
# no appreciable difference, even on suites that take ~30s to validate.

def replicate( target, source ):
    """fast deepcopy for a nested dict in which elements may be
    simple types or lists of simple types"""
    for key,val in source.items():
        if isinstance( val, dict ):
            if key not in target:
                target[key] = OrderedDict()
            replicate( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

def override( target, sparse ):
    """similar to replicate, but assumes all slots already exist in the
    target dict"""
    for key,val in sparse.items():
        if isinstance( val, dict ):
            override( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

