#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

def print_cfg( dct, level=0, indent=0, prefix='' ):
    """Recursively print a nested dict as a configobj style structure"""
    for key,val in dct.iteritems():
        if isinstance( val, dict ):
            print prefix + '   '*indent + '['*(level+1) + str(key) + ']'*(level+1)
            print_cfg( val, level=level+1, indent=indent+1, prefix=prefix)
        else:
            print prefix + '   '*indent + str(key) + ' = ' + str(val) 

