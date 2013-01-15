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

import re

def join( lines ):
    """cylc suite definition continuation line support"""
    outf = []
    cline = ''
    for line in lines:
        # detect continuation line endings
        m = re.match( '(.*)\\\$', line )
        if m:
            # add line to cline instead of appending to outf.
            cline += m.groups()[0]
        else:
            outf.append( cline + line )
            # reset cline 
            cline = ''
    return outf

