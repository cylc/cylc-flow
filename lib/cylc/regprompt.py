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

def prompt( question, default ):
    def explain():
        print "Valid responses:"
        print "  [enter] - accept the default"
        print "  VALUE   - supply a new value"
        print "  q       - quit the operation"
        print "  s       - skip this item"
        print "  ?       - print this message"

    try_again = True
    while try_again:
        try_again = False
        res = raw_input( question + " (default '" + default + "', else VALUE,q,s,?) " )
        if res == '?':
            explain()
            try_again = True
        elif res == '':
            res = default
            break
        else:
            break
    return res
 
