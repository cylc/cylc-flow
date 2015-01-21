#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
