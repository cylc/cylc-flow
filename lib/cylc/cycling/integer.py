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

"""
Integer cycling by point, interval, and sequence classes.
The same interface as for full ISO8601 date time cycling.
"""

import re

# TODO - consider copy vs reference of points, intervals, sequences
# TODO - Use context points properly


class point( object ):
    """A single point in an integer sequence."""
    def __init__( self, value ):
        self.value = int(value)
    def __str__( self ):
        return str(self.value)
    def __cmp__( self, p):
        return cmp( self.value, p.value )
    def __sub__( self, i ):
        return self.__class__( self.value - i.value )
    def __add__( self, i ):
        return self.__class__( self.value + i.value )
    def __eq__( self, i ):
        return self.value == i.value
    def __neq__( self, i ):
        return self.value != i.value


class interval( object ):
    """The interval between points in an integer sequence."""

    @classmethod
    def get_null( cls ):
        return interval(0)

    def __init__( self, value ):
        self.value = int(value)
    def is_null( self ):
        return self.value == 0
    def __str__( self ):
        return str(self.value)
    def __cmp__( self, i ):
        return cmp( self.value, i.value )
    def __add__( self, i ):
        return self.__class__( self.value + i.value )
    def __mul__( self, m ):
        # the suite runahead limit is a multiple of the smallest sequence interval
        return self.__class__( m * self.value )
    def __abs__( self ):
        return self.__class__( abs(self.value ))
    def __neg__( self ):
        return self.__class__( - self.value )


class sequence( object ):
    """
    A sequence of integer points separated by an integer interval.

    Currently implemented in terms of a step (the interval) and an
    anchor (an arbitrary fixed point on the sequence).  An offset is
    effected by shifting the anchor point.
    """

    def __init__( self, dep_section, start=None, stop=None ):
        """Parse sequence state from graph section heading."""

        self.dep_section = dep_section
        m = re.match( '^Integer\(\s*(\d+)\s*,\s*(\d+)\s*\)$', dep_section )
        if m:
            anchor, step = m.groups()
        else:
            raise Exception( "ERROR: integer cycling init!")

        self.i_offset = interval(0)

        self.p_start = self.p_stop = self.p_anchor = None
        if start:
            self.p_start = point( start )
        if stop:
            self.p_stop = point( stop )
        if anchor:
            self.p_anchor = point( anchor )

        self.i_step = interval( step )

    def set_offset( self, i ):
        """Alter state to offset the entire sequence."""
        self.i_offset = i
        self.p_anchor += self.i_offset

    def get_offset( self ):
        return self.i_offset

    def get_interval( self ):
        return self.i_step

    def is_on_sequence( self, p ):
        return ( p.value - self.p_anchor.value ) % self.i_step.value == 0

    def get_prev_point( self, p ):
        # may be None if out of the recurrence bounds
        i = ( p.value - self.p_anchor.value ) % self.i_step.value
        if i:
            p_prev = p - interval( i )
        else:
            p_prev = p - self.i_step
        if self.p_start and p_prev.value < self.p_start.value:
            return None
        else:
            return p_prev

    def get_next_point( self, p ):
        # may be None if out of the recurrence bounds
        pts = []
        i = ( p.value - self.p_anchor.value ) % self.i_step.value
        p_next = p + self.i_step - interval( i )
        if self.p_stop and p_next.value > self.p_stop.value:
            return None
        else:
            return p_next

    def get_nexteq_point( self, p ):
        # TODO - should upgrade p to start_point if nec?
        i = ( p.value - self.p_anchor.value ) % self.i_step.value
        if i:
            p_nexteq = p + self.i_step - interval( i )
        else:
            p_nexteq = p
        if self.p_stop and p_nexteq.value > self.p_stop.value:
            return None
        else:
            return p_nexteq

    def __eq__( self, seq ):
        return self.i_offset == seq.i_offset and \
               self.i_step == seq.i_step and \
               self.dep_section == seq.dep_section and \
               self.p_start == seq.p_start and \
               self.p_stop == seq.p_stop and \
               self.p_anchor == seq.p_anchor 

    def dump( self ):
        print 
        print self.dep_section
        print '  step  ', self.i_step
        print '  anchor', self.p_anchor
        print '  offset', self.i_offset
        print '  start ', self.p_start
        print '  stop  ', self.p_stop


if __name__ == '__main__':

    p = point( '9' )
    i = interval( '3' )
    print p - i 
    print p + i 

    r = sequence( 'Integer( 13,3 )' )
    r.set_offset( interval('-1') )
    start = r.get_nexteq_point( point('7') )
    stop = point('22')
    print
    while p < stop:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_next_point( p )
    print 
    while p >= start:
        print ' + ' + str(p), r.is_on_sequence(p)
        p = r.get_prev_point( p )
 
    print
    print r.is_on_sequence( point('11') )

    print
    q = sequence( 'Integer( 13,3 )' )
    q.set_offset( interval('-1') )
    print r == q
    q.set_offset( interval('-2') )
    print r == q

