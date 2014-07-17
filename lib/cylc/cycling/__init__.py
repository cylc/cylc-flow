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

"""This module provides base classes for cycling data objects."""


class CyclerTypeError(TypeError):

    """An error raised when incompatible cycling types are wrongly mixed."""

    ERROR_MESSAGE = "Incompatible cycling types: {0} ({1}), {2} ({3})"

    def __str__(self):
        return self.ERROR_MESSAGE.format(*self.args)


class PointBase(object):

    """The base class for single points in a cycler sequence.

    Points should be based around a string value.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide self.cmp_, self.sub, self.add, and
    self.eq methods which should behave as __cmp__, __sub__,
    etc standard comparison methods. Note: "cmp_" not "cmp".
    
    Subclasses may also provide an overridden self.standardise
    method to reprocess their value into a standard form.

    """

    TYPE = None
    TYPE_SORT_KEY = None

    def __init__(self, value):
        if not isinstance(value, basestring):
            raise TypeError(type(value))
        self.value = value

    def add(self, other):
        """Add other to self, returning a PointBase-derived object."""
        raise NotImplementedError()

    def cmp_(self, other):
        """Compare self to other, returning a Python 'cmp'-like result."""
        raise NotImplementedError()

    def standardise(self):
        """Format self.value into a standard representation."""
        return self

    def sub(self, other):
        """Subtract other from self, returning a Point or Interval.

        If other is a Point, return an Interval.
        If other is an Interval, return a Point.

        ('Point' here is a PointBase-derived object, and 'Interval' an
         IntervalBase-derived object)

        """
        raise NotImplementedError()

    def __str__(self):
        return self.value

    def __cmp__(self, other):
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self.cmp_(other)

    def __sub__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __add__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.add(other)


class IntervalBase(object):

    """An interval separating points in a cycler sequence.

    Intervals should be based around a string value.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide self.cmp_, self.sub, self.add,
    self.__mul__, self.__abs__, self.__nonzero__ methods which should
    behave as __cmp__, __sub__, etc standard comparison methods.

    They can also just override the provided comparison methods (such
    as __cmp__) instead.

    Note: "cmp_" not "cmp", etc. They should also provide:
     * self.get_null, which is a method to extract the null interval of
    this type.
     * self.get_inferred_child to generate an offset from an input
    without units using the current units of the instance (if any).

    Subclasses may also provide an overridden self.standardise
    method to reprocess their value into a standard form.

    """

    TYPE = None
    TYPE_SORT_KEY = None


    @classmethod
    def get_null(cls):
        """Return a null interval."""
        raise NotImplementedError()

    def get_inferred_child(self, string):
        """For a given string, infer the offset given my instance units."""
        raise NotImplementedError()

    def __abs__( self ):
        raise NotImplementedError()

    def __mul__( self, factor ):
        raise NotImplementedError()

    def __nonzero__(self):
        raise NotImplementedError()

    def __init__(self, value):
        if not isinstance(value, basestring):
            raise TypeError(type(value))
        self.value = value

    def add(self, other):
        """Add other to self, returning a Point or Interval.

        If other is a Point, return a Point.
        If other is an Interval, return an Interval..

        ('Point' here is a PointBase-derived object, and 'Interval' an
         IntervalBase-derived object)

        """
        raise NotImplementedError()

    def cmp_(self, other):
        """Compare self to other, returning a Python 'cmp'-like result."""
        raise NotImplementedError()

    def standardise(self):
        """Format self.value into a standard representation."""
        return self

    def sub(self, other):
        """Subtract other from self; return an IntervalBase-derived object."""
        raise NotImplementedError()

    def is_null( self ):
        return (self == self.get_null())

    def __str__( self ):
        return self.value

    def __add__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.add(other)

    def __cmp__(self, other):
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self.cmp_(other)

    def __sub__(self, other):
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __neg__( self ):
        return self * -1
