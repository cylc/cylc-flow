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

class CyclerTypeError(TypeError):

    """An error raised when incompatible cycling types are wrongly mixed."""

    ERROR_MESSAGE = "Incompatible cycling types: {0} ({1}), {2} ({3})"

    def __str__(self):
        return self.ERROR_MESSAGE.format(*self.args)


class PointBase(object):

    """The base class for single points in a cycler sequence.

    Points should be initalised with, and based around, a string
    value.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide self.cmp_, self.sub, self.add, and
    self.eq methods which should behave as __cmp__, __sub__,
    etc standard comparison methods. Note: "cmp_" not "cmp".

    """

    TYPE = None
    TYPE_SORT_KEY = None

    def __init__(self, value):
        if not isinstance(value, basestring):
            raise TypeError(type(value))
        self.value = value

    def __str__(self):
        return self.value

    def __cmp__(self, p):
        if self.TYPE != p.TYPE:
            return cmp(self.TYPE_SORT_KEY, p.TYPE_SORT_KEY)
        return self.cmp_(p)

    def __sub__(self, i):
        if self.TYPE != i.TYPE:
            raise CyclerTypeError(self.TYPE, self, i.TYPE, i)
        return self.sub(i)

    def __add__(self, i):
        if self.TYPE != i.TYPE:
            raise CyclerTypeError(self.TYPE, self, i.TYPE, i)
        return self.add(i)


class IntervalBase(object):

    """An interval separating points in a cycler sequence."""

    TYPE = None
    TYPE_SORT_KEY = None

    @classmethod
    def get_null(self):
        raise NotImplementedError()

    def __init__(self, value):
        if not isinstance(value, basestring):
            raise TypeError(value)
        self.value = value

    def is_null( self ):
        return (self == self.get_null())

    def __str__( self ):
        return self.value

    def __cmp__(self, i):
        if self.TYPE != i.TYPE:
            return cmp(self.TYPE_SORT_KEY, i.TYPE_SORT_KEY)
        return self.cmp_(i)

    def __sub__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __add__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.add(other)

    def __mul__( self, m ):
        # the suite runahead limit is a multiple of the smallest sequence interval
        raise NotImplementedError()

    def __abs__( self ):
        raise NotImplementedError()

    def __neg__( self ):
        return self * -1
