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

import os, sys

def print_nested( dct, level=0, indent=0, prefix='', omitNone=False ):
    """
    Recursively print a nested dict in nested INI format.
    """
    delayed=[]
    for key,val in dct.items():
        if isinstance( val, dict ):
            # print top level items before recursing
            delayed.append((key,val))
        elif val != None:
            if isinstance( val, list ):
                v = ', '.join([str(f) for f in val])
            else:
                v = str(val)
            print prefix + '   '*indent + str(key) + ' = ' + v
    for key,val in delayed:
        if val != None:
            print prefix + '   '*indent + '['*(level+1) + str(key) + ']'*(level+1)
        print_nested( val, level=level+1, indent=indent+1, prefix=prefix, omitNone=omitNone)

