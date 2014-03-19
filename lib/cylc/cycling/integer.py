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

# TODO - can args of get_next()-like methods be assumed on-sequence?
# TODO - consider copy vs reference of points, intervals, sequences
# TODO - does set_offset() need to recompute bounds in-context?
# TODO - truncated integer recurrence notation?
# TODO - handle cross-recurrence triggers properly (e.g. dependence of
#           cycling tasks on start-up tasks.)

#___________________________
# INTEGER RECURRENCE REGEXES
#
# Intended to be integer analogues of the ISO8601 date time notation.
# For cycle points a special character 'c' means "context supplied";
# if missing, context is required: the suite start and stop points.
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
        # the suite runahead limit is a multiple of the smallest sequence interval
        return self.__class__( m * self.value )
    def __abs__( self ):
        return self.__class__( abs(self.value ))
    def __neg__( self ):
        return self.__class__( - self.value )


class sequence( object ):
    """A sequence of integer points separated by an integer interval."""

    def __init__( self, dep_section, p_context_start, p_context_stop=None ):
        """Parse sequence state from graph section heading."""

        self.dep_section = dep_section

        # store context 
        self.p_context_start = point(p_context_start)
        if p_context_stop:
            self.p_context_stop  = point(p_context_stop)

        # state variables
        self.p_start = None
        self.p_stop  = None
        self.i_step  = None
        self.i_offset = interval('0')
 
        # 1) REPEAT/START/PERIOD: R([n])/([c])(i)/P(i)
        m = FULL_RE_1.match( dep_section )
        if m:
            n, c, start, step = m.groups()
            # step
            self.i_step = interval( step )
            # start
            if c == 'c':
                self.p_start = point( start )
            else:
                self.p_start = self.p_context_start + point( start )
            # stop
            if n:
                p = self.p_start + self.i_step * ( int(n) - 1 )
                if p <= self.p_context_stop:
                    self.p_stop = p
                else:
                    self.p_stop = self._get_preveq_point( self.p_context_stop, p_ref=self.p_start )
            else:
                self.p_stop = self._get_preveq_point( self.p_context_stop, p_ref=self.p_start )

        else:
            # 2) REPEAT/START/STOP: R(n)/([c])(i)/([c])(i)
            m = FULL_RE_2.match( dep_section )
            if m:
                n, c1, start, c2, stop = m.groups()
                # start
                if c1 == 'c':
                    self.p_start = point( start )
                else:
                    self.p_start = self.p_context_start + point( start )
                # stop
                if c2 == 'c':
                    self.p_stop = point( stop )
                elif self.p_context_stop:
                    self.p_stop = self.p_context_stop + point( stop )
                else:
                    raise "ERROR: stop or stop context required with regex 2"
                # step
                self.i_step = interval( ( self.p_stop.value - self.p_start.value )/int(n) + 1 )

            else:
                # 3) REPEAT/PERIOD/STOP: R(n)/P(i)/([c])i
                m = FULL_RE_3.match( dep_section )
                if m:
                    n, step, c, stop = m.groups()
                    # step
                    self.i_step = interval( step )
                    # stop
                    if c == 'c':
                        self.p_stop = point( stop )
                    elif self.p_context_stop:
                        self.p_stop = self.p_context_stop + point( stop )
                    else:
                        raise "ERROR: stop or stop context required with regex 2"
                    # start
                    self.p_start = self.p_stop - self.i_step * ( int(n) - 1 )

                else:
                    raise Exception( "ERROR in integer cycling initialization")

        if self.p_start < self.p_context_start:
            # start from first point >= context start
            r = ( self.p_context_start.value - self.p_start.value ) % self.i_step.value
            self.p_start = self.p_context_start + interval(r)
        if self.p_stop and self.p_context_stop and self.p_stop > self.p_context_stop:
            # stop at first point <= context stop
            r = ( self.p_context_stop.value - self.p_start.value ) % self.i_step.value
            self.p_stop = self.p_context_stop - self.i_step + interval(r)

    def set_offset( self, i_offset ):
        # shift the sequence by i_offset
        if i_offset == self.i_step:
            # nothing to do
            return
        self.i_offset = i_offset
        # all points are calculated relative to self.p_start
        self.p_start += interval( self.i_step.value % i_offset.value )

    def _is_in_bounds( self, p, use_context=False ):
        if use_context:
            min = self.p_context_start
            max = self.p_context_stop
        else:
            min = self.p_start
            max = self.p_stop
        if p >= min and p <= max:
            return True
        else:
            return False

    def is_on_sequence( self, p ):
        return ( p.value - self.p_start.value ) % self.i_step.value == 0

    def is_valid( self, p ):
        return self._is_in_bounds(p) and self.is_on_sequence(p)

    def get_offset( self ):
        return self.i_offset

    def get_interval( self ):
        return self.i_step

    def get_prev_point( self, p ):
        # get prev point < p
        i = ( p.value - self.p_start.value ) % self.i_step.value
        if i:
            p_prev = p - interval(i)
        else:
            p_prev = p - self.i_step
        if self._is_in_bounds( p_prev ):
            return p_prev
        else:
            return None

    def get_next_point( self, p ):
        # get next point > p
        i = ( p.value - self.p_start.value ) % self.i_step.value
        p_next = p + self.i_step - interval(i)
        if self._is_in_bounds( p_next ):
            return p_next
        else:
            return None

    def get_nexteq_point( self, p ):
        # TODO - rename or replace this? (in the new framework for
        # start-up we already know the first on-sequence point. Is
        # also used get_graph_raw() though?)
        if p < self.p_start:
            return self.p_start
        else:
            return p

    def _get_preveq_point( self, p, p_ref ):
        # return the on-sequence point <= p
        r = ( p.value - p_ref.value ) % self.i_step.value
        return p - self.i_step + interval(r)
 
    def get_start( self ):
        return self.p_start

    def get_stop( self ):
        return self.p_stop

    def __eq__( self, q ):
        return self.dep_section == q.dep_section and \
                self.i_offset == q.i_offset and \
                self.i_step == q.i_step and \
                self.p_start == q.p_start and \
                self.p_stop == q.p_stop


if __name__ == '__main__':

    r = sequence( 'R/2/P2', 1, 10 )
    #r = sequence( 'R/c2/P2', 1, 10 )
    #r = sequence( 'R2/c2/P2', 1, 10 )
    #r = sequence( 'R2/c4/c6', 1, 10 )
    #r = sequence( 'R2/P2/c6', 1, 10 )

    r.set_offset( interval('-1') )

    start = r.get_start()
    stop = r.get_stop()

    p = start
    while p and p <= stop:
        print ' + ' + str(p)
        p = r.get_next_point( p )
    print 

    p = stop
    while p and p >= start:
        print ' + ' + str(p)
        p = r.get_prev_point( p )
 
    print
    print r.is_on_sequence( point('11') )
    print r._is_in_bounds( point('11') )
    print r.is_valid( point('11') )

    print
    q = sequence( 'R/1/P1', 1, 10 )
    print r == q
    q.set_offset( interval('-2') )
    print r == q

