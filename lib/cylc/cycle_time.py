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
import re
from cylc.strftime import strftime
from wallclock import now

"""
CYCLE TIME: YYYY[MM[DD[HH[mm[ss]]]]]
"""

MEMOIZE_LIMIT = 10000


class CycleTimeError( Exception ):
    """
    Attributes:
        message - what the problem is.
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class InvalidCycleTimeError( CycleTimeError ):
    pass

class at( object ):
    """asynchronous tag: integer"""
    def __init__( self, tag ):
        self.value = tag

    def get( self ):
        return str(self.value)

class ct( object ):
    """YYYY[MM[DD[HH[mm[ss]]]]]"""
    # template:
    YYYYMMDDHHmmss = '00010101000000'

    def __init__( self, ctin ):
        if isinstance( ctin, datetime.datetime ):
            self.parse( self._init_by_datetime( ctin ) )
        else:
            self.parse( ctin )

    def _init_by_datetime( self, dtvalue ):
        return strftime( dtvalue, "%Y%m%d%H%M%S" )

    def parse( self, strx ):
        if strx == "now":
            strx = now().strftime("%Y%m%d%H%M%S")
        n = len(strx)
        if n == 4 or n == 6 or n == 8 or n == 10 or n == 12 or n == 14:
            self.strvalue = strx + ct.YYYYMMDDHHmmss[n:]
        else:
            raise InvalidCycleTimeError, 'ERROR: Illegal cycle time (YYYY[MM[DD[HH[mm[ss]]]]]): ' + strx

        #self.strvalue_Y2H = self.strvalue[0:10]

        self.year    = self.strvalue[ 0:4 ]
        self.month   = self.strvalue[ 4:6 ]
        self.day     = self.strvalue[ 6:8 ]
        self.hour    = self.strvalue[ 8:10]
        self.minute  = self.strvalue[10:12]
        self.seconds = self.strvalue[12:14]
        self.HHmmss  = self.strvalue[ 8:14 ]
        self.DDHHmmss  = self.strvalue[ 6:14 ]
        self.MMDDHHmmss  = self.strvalue[ 4:14 ]

        # convert to datetime as a validity check
        try:
            self.dtvalue = datetime.datetime( int(self.year), int(self.month),
                int(self.day), int(self.hour), int(self.minute),
                int(self.seconds))
        except ValueError,x:
            # returns sensible messages: "minute must be in 0..59"
            raise InvalidCycleTimeError( x.__str__() + ': ' + self.get_formatted() )

    def get( self ):
        #### TODO - INTEGER CTIME COMPARISONS REQUIRE USE OF SAME NUMBER
        #### OF DIGITS EVERYWHERE
        #return self.strvalue
        return self.strvalue[0:10] # just YYYYMMDDHH for now

    def get_formatted( self ):
        # YYYY/MM/DD HH:mm:ss
        return self.year + '/' + self.month + '/' + self.day + ' ' + \
                self.hour + ':' + self.minute + ':' + self.seconds

    def get_datetime( self ):
        return self.dtvalue

    def _str_from_datetime( self, dt ):
        return strftime( dt, "%Y%m%d%H%M%S" )

    def increment( self, weeks=0, days=0, hours=0, minutes=0, seconds=0,
            microseconds=0, milliseconds=0 ):
        # Can't increment by years or months easily - they vary in length.
        newdt = self.dtvalue + \
                datetime.timedelta( int(days), int(seconds),
                        int(microseconds), int(milliseconds),
                        int(minutes), int(hours), int(weeks) )
        self.parse( self._str_from_datetime( newdt ))

    def decrement( self, weeks=0, days=0, hours=0, minutes=0, seconds=0,
            microseconds=0, milliseconds=0 ):
        # Can't decrement by years or months easily - they vary in length.
        newdt = self.dtvalue - \
                datetime.timedelta( int(days), int(seconds),
                        int(microseconds), int(milliseconds),
                        int(minutes), int(hours), int(weeks) )
        self.parse( self._str_from_datetime( newdt ))

    def clone( self ):
        return ct( self.strvalue )

    def subtract( self, ct ):
        # subtract this ct from me, return a timedelta
        # (.days, .seconds, .microseconds)
         return self.dtvalue - ct.dtvalue

    def subtract_hrs( self, ct ):
        # subtract this ct from me, return hours
        delta = self.subtract(ct)
        return int( delta.days * 24 + delta.seconds / 3600 + delta.microseconds / ( 3600 * 1000000 ))


def memoize(function):
    """This stores results for a given set of inputs to a function.

    The inputs and results of the function must be immutable.
    Keyword arguments are not allowed.

    To avoid memory leaks, only the first 10000 separate input
    permutations are cached for a given function.

    """
    inputs_results = {}
    def _wrapper(*args):
        try:
            return inputs_results[args]
        except KeyError:
            results = function(*args)
            if len(inputs_results) > MEMOIZE_LIMIT:
                # Full up, no more room.
                return results
            inputs_results[args] = results
            return results
    return _wrapper


@memoize
def ctime_cmp(ctime_str_1, ctime_str_2):
    """Compare (cmp) two cycle time strings numerically."""
    try:
        ctime_1 = ct(ctime_str_1).get()
    except InvalidCycleTimeError:
        ctime_1 = ctime_str_1
    try:
        ctime_2 = ct(ctime_str_2).get()
    except InvalidCycleTimeError:
        ctime_2 = ctime_str_2
    return cmp(int(ctime_1), int(ctime_2))


@memoize
def ctime_ge(ctime_str_1, ctime_str_2):
    return ctime_cmp(ctime_str_1, ctime_str_2) in [0, 1]


@memoize
def ctime_gt(ctime_str_1, ctime_str_2):
    return ctime_cmp(ctime_str_1, ctime_str_2) == 1


@memoize
def ctime_le(ctime_str_1, ctime_str_2):
    return ctime_cmp(ctime_str_1, ctime_str_2) in [-1, 0]


@memoize
def ctime_lt(ctime_str_1, ctime_str_2):
    return ctime_cmp(ctime_str_1, ctime_str_2) == -1
