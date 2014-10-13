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

import datetime

def strftime( dt, template ):
    """A replacement for datetime.strftime() which does not handle dates
    earlier than 1900 (or beyond 2048?)."""

    iso = dt.isoformat()
    return isoformat_strftime( iso, template )


def isoformat_strftime( iso_string, template ):
    """Re-template a datetime.datetime isoformat string."""
    d,t = iso_string.split('T')
    Y,m,d = d.split('-')
    H,M,S = t.split(':')
    t = template.replace('%Y', Y )
    t = t.replace('%m', m )
    t = t.replace('%d', d )
    t = t.replace('%H', H )
    t = t.replace('%M', M )
    t = t.replace('%S', S[0:2] )
    return t


if __name__ == '__main__':
    dt1 = datetime.datetime(1900,1,1)
    dt2 = datetime.datetime(1600,1,1)

    print strftime( dt1, "%Y-%m-%d %H:%M:%S" )
    print dt1.strftime( "%Y-%m-%d %H:%M:%S" )

    print strftime( dt2, "%Y-%m-%d %H:%M:%S" )
    print dt2.strftime( "%Y-%m-%d %H:%M:%S" ) # FAILS
