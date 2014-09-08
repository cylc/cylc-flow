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


class PointParsingError(ValueError):

    """An error raised when a point has an incorrect value."""

    ERROR_MESSAGE = "Incompatible value for {0}: {1}: {2}"

    def __str__(self):
        return self.ERROR_MESSAGE.format(*self.args)


class IntervalParsingError(ValueError):

    """An error raised when an interval has an incorrect value."""

    ERROR_MESSAGE = "Incompatible value for {0}: {1}"

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
        """Add other (interval) to self, returning a point."""
        raise NotImplementedError()

    def cmp_(self, other):
        """Compare self to other point, returning a 'cmp'-like result."""
        raise NotImplementedError()

    def standardise(self):
        """Format self.value into a standard representation and check it."""
        return self

    def sub(self, other):
        """Subtract other (interval or point), returning a point or interval.

        If other is a Point, return an Interval.
        If other is an Interval, return a Point.

        ('Point' here is a PointBase-derived object, and 'Interval' an
         IntervalBase-derived object)

        """
        raise NotImplementedError()

    def __str__(self):
        # Stringify.
        return self.value

    def __cmp__(self, other):
        # Compare to other point.
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self.cmp_(other)

    def __sub__(self, other):
        # Subtract other (point or interval) from self.
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __add__(self, other):
        # Add other (point or interval) from self.
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
     * self.get_null_offset, which is a method to extract a null offset
    relative to a PointBase object.
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

    def __abs__(self):
        # Return an interval with absolute values for all properties.
        raise NotImplementedError()

    def __mul__(self, factor):
        # Return an interval with all properties multiplied by factor.
        raise NotImplementedError()

    def __nonzero__(self):
        # Return True if the interval has any non-zero properties.
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
        """Compare self to other (interval), returning a 'cmp'-like result."""
        raise NotImplementedError()

    def standardise(self):
        """Format self.value into a standard representation."""
        return self

    def sub(self, other):
        """Subtract other (interval) from self; return an interval."""
        raise NotImplementedError()

    def is_null(self):
        return (self == self.get_null())

    def __str__(self):
        # Stringify.
        return self.value

    def __add__(self, other):
        # Add other (point or interval) to self.
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.add(other)

    def __cmp__(self, other):
        # Compare self to other (interval).
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self.cmp_(other)

    def __sub__(self, other):
        # Subtract other (interval or point) from self.
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __neg__(self):
        # Return an interval with all properties multiplied by -1.
        return self * -1


class SequenceBase(object):

    """The base class for cycler sequences.

    Subclasses should accept a sequence-specific string, a
    start context string, and a stop context string as
    constructor arguments.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide get_async_expr, get_interval,
    get_offset & set_offset (deprecated), is_on_sequence,
    _get_point_in_bounds, is_valid, get_prev_point,
    get_nearest_prev_point, get_next_point,
    get_next_point_on_sequence, get_first_point, and
    get_stop_point.

    They should also provide a self.__eq__ implementation
    which should return whether a SequenceBase-derived object
    is equal to another (represents the same set of points).

    """

    TYPE = None
    TYPE_SORT_KEY = None

    @classmethod
    def get_async_expr(cls, start_point=0):
        """Express a one-off sequence at the initial cycle point."""
        raise NotImplementedError()

    def __init__(self, sequence_string, context_start, context_stop=None):
        """Parse sequence string according to context point strings."""
        pass

    def get_interval(self):
        """Return the cycling interval of this sequence."""
        raise NotImplementedError()

    def get_offset(self):
        """Deprecated: return the offset used for this sequence."""
        raise NotImplementedError()

    def set_offset(self, i_offset):
        """Deprecated: alter state to offset the entire sequence."""
        raise NotImplementedError()

    def is_on_sequence(self, point):
        """Is point on-sequence, disregarding bounds?"""
        raise NotImplementedError()

    def _get_point_in_bounds(self, point):
        """Return point, or None if out of bounds."""
        raise NotImplementedError()

    def is_valid(self, point):
        """Is point on-sequence and in-bounds?"""
        raise NotImplementedError()

    def get_prev_point(self, point):
        """Return the previous point < point, or None if out of bounds."""
        raise NotImplementedError()

    def get_nearest_prev_point(self, point):
        """Return the largest point < some arbitrary point."""
        raise NotImplementedError()

    def get_next_point(self, point):
        """Return the next point > point, or None if out of bounds."""
        raise NotImplementedError()

    def get_next_point_on_sequence(self, point):
        """Return the next point > point assuming that point is on-sequence,
        or None if out of bounds."""
        raise NotImplementedError()

    def get_first_point(self, point):
        """Return the first point >= to point, or None if out of bounds."""
        raise NotImplementedError()

    def get_stop_point(self):
        """Return the last point in this sequence, or None if unbounded."""
        raise NotImplementedError()

    def __eq__(self, other):
        # Return True if other (sequence) is equal to self.
        raise NotImplementedError()
