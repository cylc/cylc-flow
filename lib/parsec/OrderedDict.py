#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

"""Ordered Dictionary data structure used extensively in cylc."""

try:
    # first try the fast ordereddict C implementation.
    # DOWNLOAD: http://anthon.home.xs4all.nl/Python/ordereddict/
    # According to the ordereddict home page, this is much faster than
    # collections.OrderedDict.
    from _ordereddict import ordereddict as OrderedDict
except ImportError:
    try:
        # then try Python 2.7+ native module
        from collections import OrderedDict
    except ImportError:
        # then try the pre-2.7 backport from ActiveState
        # (packaged with cylc)
        from OrderedDictCompat import OrderedDict

