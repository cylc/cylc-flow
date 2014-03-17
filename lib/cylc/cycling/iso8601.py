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

import re
from isodatetime.parsers import TimePointParser, TimeIntervalParser
from cylc.time_parser import CylcTimeParser

# TODO - RESTORE MEMOIZATION FOR TIME POINT COMPARISONS
# TODO - Consider copy vs reference of points, intervals, sequences
# TODO - Use context points properly
# TODO - ignoring anchor in back-compat sections


class point( object ):
    """A single point in an ISO8601 date time sequence."""
    def __init__( self, value ):
        self.value = TimePointParser().parse(value)
    def __str__( self ):
        return str(self.value)
    def __cmp__( self, p):
        return cmp( self.value, p.value )
    def __sub__( self, i ):
        return self.__class__( str( self.value - i.value ) )
    def __add__( self, i ):
        return self.__class__( str( self.value + i.value ) )
    def __eq__( self, i ):
        return self.value == i.value
    def __neq__( self, i ):
        return self.value != i.value


class interval( object ):
    """The interval between points in an ISO8601 date time sequence."""

    @classmethod
    def get_null( cls ):
        return interval('P0Y')

    def __init__( self, value ):
        self.value = TimeIntervalParser().parse(value)
    def is_null( self ):
        return self.value == self.__class__.get_null()
    def __str__( self ):
        return str(self.value)
    def __cmp__( self, i ):
        return cmp( self.value, i.value )
    def __add__( self, i ):
        return self.__class__( str( self.value + i.value) )
    def __mul__( self, m ):
        # the suite runahead limit is a multiple of the smallest sequence interval
        return self.__class__( str(self.value * m ))
    def __abs__( self ):
        # hack: TimeIntervalParser can't parse str( TimeInterval * -1 )
        # (if self.value has already been through __neg__)
        res = self.__class__.get_null()
        if self.value < self.__class__.get_null().value:
            res.value = self.value * -1
        return res
    def __neg__( self ):
        # hack: TimeIntervalParser can't parse str( TimeInterval * -1 )
        res = self.__class__(str(self.value))
        res.value = res.value * -1
        return res


class sequence( object ):
    """
    A sequence of ISO8601 date time points separated by an interval.
    """

    def __init__( self, dep_section, context_start_point=None, context_end_point=None ):

        self.dep_section = dep_section

        self.context_start_point = context_start_point
        self.context_end_point = context_end_point

        self.offset = interval.get_null()

        i = None
        m = re.match( '^Daily\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section )
        if m:
            # back compat Daily()
            anchor, step = m.groups()
            i = 'P' + step + 'D'
        else:
            m = re.match( '^Monthly\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section )
            if m:
                # back compat Monthly()
                anchor, step = m.groups()
                i = 'P' + step + 'M'
            else:
                m = re.match( '^Yearly\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section )
                if m:
                    # back compat Yearly()
                    anchor, step = m.groups()
                    i = 'P' + step + 'Y'
                else:
                    # ISO8601
                    i = dep_section
        if not i:
            raise "ERROR: iso8601 cycling init!"

        self.time_parser = CylcTimeParser( context_start_point, context_end_point )
        self.step = interval( i )
        self.recurrence = self.time_parser.parse_recurrence( i )

    def set_offset( self, i ):
        """Alter state to offset the entire sequence."""
        self.offset = i
        res = point(self.context_start_point) + i
        self.time_parser = CylcTimeParser( str(res), self.context_end_point )
 
    def get_offset( self ):
        return self.offset

    def get_interval( self ):
        return self.step

    def is_on_sequence( self, p ):
        """Return True if p is on-sequence."""
        return self.recurrence.get_is_valid( p.value )

    def get_prev_point( self, p ):
        # may be None if out of the recurrence bounds
        res = None
        prv = self.recurrence.get_prev( p.value )
        if prv:
            res = point(str(prv))
        return res

    def get_next_point( self, p ):
        # may be None if out of the recurrence bounds
        res = None
        nxt = self.recurrence.get_next( p.value )
        if nxt:
            res = point(str(nxt))
        return res

    def get_nexteq_point( self, p ):
        """return the on-sequence point greater than or equal to p."""
        # TODO - NOT IMPLEMENTED
        #   if p < Tstart return Tstart, else iterate until >= p?
        return p

    def __eq__( self, seq ):
        # TODO - IMPLEMENT THIS TO AVOID HOLDING DUPLICATE SEQUENCES IN TASKS
        return False


if __name__ == '__main__':

    p_start = point( '20100808T00' )
    p_stop = point( '20100808T02' )
    i = interval( 'PT6H' )
    print p_start - i 
    print p_stop + i 

    print
    r = sequence( 'PT10M', str(p_start), str(p_stop), )
    r.set_offset( - interval('PT10M') )
    p = r.get_nexteq_point( point('20100808T0000') )
    print p
    while p and p < p_stop:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_next_point( p )
    print 
    while p and p >= p_start:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_prev_point( p )
     
    print
    print r.is_on_sequence( point('20100809T0005') )

