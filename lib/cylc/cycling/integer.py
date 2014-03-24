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

"""
Integer cycling by point, interval, and sequence classes.
The same interface as for full ISO8601 date time cycling.
"""

# TODO - consider copy vs reference of points, intervals, sequences
# TODO - truncated integer recurrence notation?
# TODO - handle cross-recurrence triggers properly
#        (e.g. dependence of cycling tasks on start-up tasks.)

#___________________________
# INTEGER RECURRENCE REGEXES
#
# Intended to be integer analogues of the ISO8601 date time notation.
#
# Unlike ISO8601 time points we can't tell if an integer point is
# absolute, or relative to some context, so a special character 'c'
# is used to signify that context is required.
#
# 1) REPEAT/START/PERIOD: R[n]/[c]i/Pi
# missing n means repeat indefinitely
FULL_RE_1 = re.compile( 'R(\d+)?/(c)?(\d+)/P(\d+)' )
#
# 2) REPEAT/START/STOP: Rn/[c]i/[c]i
# n required: n times between START and STOP
# (R1 means just START, R2 means START and STOP)
FULL_RE_2 = re.compile( 'R(\d+)/(c)?(\d+)/(c)?(\d+)' )
#
# 3) REPEAT/PERIOD/STOP: Rn/Pi/[c]i
# (n required to count back from stop)
FULL_RE_3 = re.compile( 'R(\d+)?/P(\d+)/(c)?(\d+)' )
#---------------------------


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
        return self.__class__( m * self.value )
    def __abs__( self ):
        return self.__class__( abs(self.value ))
    def __neg__( self ):
        return self.__class__( - self.value )


class sequence( object ):
    """Integer points a regular interval."""

    def __init__( self, dep_section, p_context_start, p_context_stop=None ):
        """Parse state (start, stop, interval) from a graph section heading.
        The start and stop points are always on-sequence, context points
        might not be. If computed start and stop points are out of bounds,
        they will be set to None. Context is used only initially, to defined 
        the sequence bounds."""

        # start context always exists
        self.p_context_start = point(p_context_start)
        # stop context may exist
        if p_context_stop:
            self.p_context_stop = point(p_context_stop)

        # state variables: start, stop, and step
        self.p_start = None
        self.p_stop  = None
        self.i_step  = None

        # offset must be stored to compute the runahead limit
        self.i_offset = interval('0')
 
        # 1) REPEAT/START/PERIOD: R([n])/([c])(i)/P(i)
        m = FULL_RE_1.match( dep_section )
        if m:
            n, c, start, step = m.groups()
            self.i_step = interval( step )
            if c == 'c':
                self.p_start = self.p_context_start + point( start )
            else:
                self.p_start = point( start )
            if n:
                self.p_stop = self.p_start + self.i_step * ( int(n) - 1 )
            elif self.p_context_stop:
                # stop at the point <= self.p_context_stop
                # use p_start as an on-sequence reference
                r = ( self.p_context_stop.value - self.p_start.value ) % self.i_step.value
                self.p_stop = self.p_context_stop - interval(r)

        else:
            # 2) REPEAT/START/STOP: R(n)/([c])(i)/([c])(i)
            m = FULL_RE_2.match( dep_section )
            if m:
                n, c1, start, c2, stop = m.groups()
                if c1 == 'c':
                    self.p_start = self.p_context_start + point( start )
                else:
                    self.p_start = point( start )
                if c2 == 'c':
                    if self.p_context_stop:
                        self.p_stop = self.p_context_stop + point( stop )
                    else:
                        raise Exception( "ERROR: stop or stop context required with regex 2" )
                else:
                    self.p_stop = point( stop )
                self.i_step = interval( ( self.p_stop.value - self.p_start.value )/int(n) + 1 )

            else:
                # 3) REPEAT/PERIOD/STOP: R(n)/P(i)/([c])i
                m = FULL_RE_3.match( dep_section )
                if m:
                    n, step, c, stop = m.groups()
                    self.i_step = interval( step )
                    if c == 'c':
                        if self.p_context_stop:
                            self.p_stop = self.p_context_stop + point( stop )
                        else:
                            raise Exception( "ERROR: stop or stop context required with regex 2" )
                    else: 
                        self.p_stop = point( stop )
                    self.p_start = self.p_stop - self.i_step * ( int(n) - 1 )

                else:
                    raise Exception( "ERROR, bad integer cycling format:" + dep_section )

        if self.i_step < interval.get_null():
            # (TODO - this should be easy to handle but needs testing)
            raise Exception( "ERROR, negative intervals not supported yet: " + self.i_step )

        if self.p_start < self.p_context_start:
            # start from first point >= context start
            r = ( self.p_context_start.value - self.p_start.value ) % self.i_step.value
            self.p_start = self.p_context_start + interval(r)

        if self.p_stop and self.p_context_stop and self.p_stop > self.p_context_stop:
            # stop at first point <= context stop
            r = ( self.p_context_stop.value - self.p_start.value ) % self.i_step.value
            self.p_stop = self.p_context_stop - self.i_step + interval(r)

    def get_interval( self ):
        return self.i_step

    def get_offset( self ):
        return self.i_offset

    def set_offset( self, i_offset ):
        """Shift the sequence by interval i_offset."""
        if not i_offset.value:
            # no offset
            return
        if not i_offset.value % self.i_step.value:
            # offset is a multiple of step
            return
        # shift to 0 < offset < interval
        i_offset = interval( i_offset.value % self.i_step.value )
        self.i_offset = i_offset
        self.p_start += i_offset # can be negative
        if self.p_start < self.p_context_start:
            self.p_start += self.i_step
        self.p_stop += i_offset
        if self.p_stop > self.p_context_stop:
            self.p_stop -= self.i_step

    def is_on_sequence( self, p ):
        """Is point p on-sequence, disregarding bounds?"""
        return ( p.value - self.p_start.value ) % self.i_step.value == 0

    def _get_point_in_bounds( self, p ):
        """Return point p, or None if out of bounds."""
        if p >= self.p_start and p <= self.p_stop:
            return p
        else:
            return None

    def is_valid( self, p ):
        """Is point p on-sequence and in-bounds?"""
        return self.is_on_sequence( p ) and \
                p >= self.p_start and p <= self.p_stop

    def get_prev_point( self, p ):
        """Return the previous point < p, or None if out of bounds."""
        # Only used in computing special sequential task prerequisites.
        i = ( p.value - self.p_start.value ) % self.i_step.value
        if i:
            p_prev = p - interval(i)
        else:
            p_prev = p - self.i_step
        return self._get_point_in_bounds( p_prev )

    def get_next_point( self, p ):
        """Return the next point > p, or None if out of bounds."""
        i = ( p.value - self.p_start.value ) % self.i_step.value
        p_next = p + self.i_step - interval(i)
        return self._get_point_in_bounds( p_next )

    def get_next_point_on_sequence( self, p ):
        """Return the next point > p assuming that p is on-sequence,
        or None if out of bounds."""
        # This can be used when working with a single sequence.
        p_next = p + self.i_step
        return self._get_point_in_bounds( p_next )

    def get_first_point( self, p ):
        """Return the first point >= to p, or None if out of bounds."""
        # Used to find the first point >= suite initial cycle time.
        if p <= self.p_start:
            p = self._get_point_in_bounds( self.p_start )
        elif self.is_on_sequence( p ):
            p  = self._get_point_in_bounds( p )
        else:
            p = self.get_next_point( self, p )
        return p

    def __eq__( self, q ):
        return self.i_step == q.i_step and \
               self.p_start == q.p_start and \
               self.p_stop == q.p_stop


if __name__ == '__main__':

    r = sequence( 'R/1/P3', 1, 10 )
    #r = sequence( 'R/c2/P2', 1, 10 )
    #r = sequence( 'R2/c2/P2', 1, 10 )
    #r = sequence( 'R2/c4/c6', 1, 10 )
    #r = sequence( 'R2/P2/c6', 1, 10 )

    r.set_offset( interval('4') )

    start = r.p_start
    stop = r.p_stop

    p = start
    while p and stop and p <= stop:
        print ' + ' + str(p)
        p = r.get_next_point( p )
    print 

    p = stop
    while p and start and p >= start:
        print ' + ' + str(p)
        p = r.get_prev_point( p )
 
    print
    r = sequence( 'R/c1/P1', 1, 10 )
    q = sequence( 'R/c1/P1', 1, 10 )
    print r == q
    q.set_offset( interval('-2') )
    print r == q

