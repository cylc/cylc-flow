# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

"""This module provides base classes for cycling data objects."""

from abc import ABCMeta, abstractmethod

from cylc.flow.exceptions import CyclerTypeError


def parse_exclusion(expr: str):
    count = expr.count('!')
    if count == 0:
        return expr, None
    elif count > 1:
        raise Exception("'%s': only one set of exclusions per expression "
                        "permitted" % expr)
    else:
        remainder, exclusions = expr.split('!')
        if (
            ',' in exclusions
            and (
                not exclusions.strip().startswith('(')
                or not exclusions.strip().endswith(')')
            )
        ):
            raise Exception(
                f"'{exclusions}': a list of exclusions must be enclosed in"
                " parentheses."
            )

        exclusions = exclusions.translate(str.maketrans('', '', ' ()'))
        exclusions = exclusions.split(',')
        return remainder.strip(), exclusions


class PointBase(metaclass=ABCMeta):

    """The abstract base class for single points in a cycler sequence.

    Points should be based around a string value.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide self._cmp, self.sub, self.add, and
    self.eq methods which should behave as __cmp__, __sub__,
    etc standard comparison methods. Note: "_cmp" not "cmp".

    Subclasses may also provide an overridden self.standardise
    method to reprocess their value into a standard form.

    """

    __slots__ = ('value')

    @property
    @abstractmethod
    def TYPE(self) -> str:
        """Cycling type of this point."""

    @property
    @abstractmethod
    def TYPE_SORT_KEY(self) -> int:
        """Used for comparison operations between different PointBase-derived
        class instances."""

    def __init__(self, value: str):
        if not isinstance(value, str):
            raise TypeError(type(value))
        self.value = value

    @abstractmethod
    def add(self, other):
        """Add other (interval) to self, returning a point."""
        pass

    @abstractmethod
    def _cmp(self, other) -> int:
        """Compare self to other point, returning a 'cmp'-like result."""
        pass

    def standardise(self) -> 'PointBase':
        """Format self.value into a standard representation and check it."""
        return self

    @abstractmethod
    def sub(self, other):
        """Subtract other (interval or point), returning a point or interval.

        If other is a Point, return an Interval.
        If other is an Interval, return a Point.

        ('Point' here is a PointBase-derived object, and 'Interval' an
         IntervalBase-derived object)

        """
        pass

    def __str__(self):
        # Stringify.
        return self.value

    __repr__ = __str__

    def __cmp__(self, other: 'PointBase') -> int:
        # Compare to other point.
        # TODO: refactor as __cmp__ not used in python3
        if other is None:
            return -1
        if not isinstance(other, PointBase):
            return NotImplemented
        # Note: apparently we can compare different subclasses of PointBase:
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self._cmp(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.__cmp__(other) == 0
        return NotImplemented

    def __lt__(self, other: 'PointBase') -> bool:
        return self.__cmp__(other) == -1

    def __le__(self, other: 'PointBase') -> bool:
        return self.__cmp__(other) <= 0

    def __gt__(self, other: 'PointBase') -> bool:
        return self.__cmp__(other) == 1

    def __ge__(self, other: 'PointBase') -> bool:
        return self.__cmp__(other) >= 0

    def __hash__(self) -> int:
        return hash(self.value)

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


class IntervalBase(metaclass=ABCMeta):

    """An interval separating points in a cycler sequence.

    Intervals should be based around a string value.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide self._cmp, self.sub, self.add,
    self.__mul__, self.__abs__ methods which should
    behave as __cmp__, __sub__, etc standard comparison methods.

    They can also just override the provided comparison methods (such
    as __cmp__) instead.

    Note: "_cmp" not "cmp", etc. They should also provide:
     * self.get_null, which is a method to extract the null interval of
    this type.
     * self.get_null_offset, which is a method to extract a null offset
    relative to a PointBase object.

    Subclasses may also provide an overridden self.standardise
    method to reprocess their value into a standard form.

    """

    __slots__ = ('value')

    @property
    @abstractmethod
    def TYPE(self) -> str:
        """Cycling type of this interval."""

    @property
    @abstractmethod
    def TYPE_SORT_KEY(self) -> int:
        """Used for comparison operations between different
        IntervalBase-derived class instances."""

    @classmethod
    @abstractmethod
    def get_null(cls):
        """Return a null interval."""
        pass

    @abstractmethod
    def __abs__(self):
        # Return an interval with absolute values for all properties.
        pass

    @abstractmethod
    def __mul__(self, factor):
        # Return an interval with all properties multiplied by factor.
        pass

    def __init__(self, value):
        if not isinstance(value, str):
            raise TypeError(type(value))
        self.value = value

    @abstractmethod
    def add(self, other):
        """Add other to self, returning a Point or Interval.

        If other is a Point, return a Point.
        If other is an Interval, return an Interval..

        ('Point' here is a PointBase-derived object, and 'Interval' an
         IntervalBase-derived object)

        """
        pass

    @abstractmethod
    def _cmp(self, other):
        """Compare self to other (interval), returning a 'cmp'-like result."""
        pass

    def standardise(self):
        """Format self.value into a standard representation."""
        return self

    @abstractmethod
    def sub(self, other):
        """Subtract other (interval) from self; return an interval."""
        pass

    def is_null(self):
        return (self == self.get_null())

    def __str__(self) -> str:
        # Stringify.
        return self.value

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self}>"

    def __add__(self, other):
        # Add other (point or interval) to self.
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.add(other)

    def __cmp__(self, other: 'IntervalBase') -> int:
        # Compare self to other (interval).
        # TODO: refactor as __cmp__ not used in python3
        if other is None:
            return -1
        if not isinstance(other, IntervalBase):
            return NotImplemented
        # Note: apparently we can compare different subclasses of IntervalBase:
        if self.TYPE != other.TYPE:
            return cmp(self.TYPE_SORT_KEY, other.TYPE_SORT_KEY)
        if self.value == other.value:
            return 0
        return self._cmp(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.__cmp__(other) == 0
        return NotImplemented

    def __lt__(self, other: 'IntervalBase') -> bool:
        return self.__cmp__(other) == -1

    def __le__(self, other: 'IntervalBase') -> bool:
        return self.__cmp__(other) <= 0

    def __gt__(self, other: 'IntervalBase') -> bool:
        return self.__cmp__(other) == 1

    def __ge__(self, other: 'IntervalBase') -> bool:
        return self.__cmp__(other) >= 0

    def __hash__(self) -> int:
        return hash(self.value)

    def __sub__(self, other):
        # Subtract other (interval or point) from self.
        if self.TYPE != other.TYPE:
            raise CyclerTypeError(self.TYPE, self, other.TYPE, other)
        return self.sub(other)

    def __neg__(self):
        # Return an interval with all properties multiplied by -1.
        return self * -1


class SequenceBase(metaclass=ABCMeta):

    """The abstract base class for cycler sequences.

    Subclasses should accept a sequence-specific string, a
    start context string, and a stop context string as
    constructor arguments.

    Subclasses should provide values for TYPE and TYPE_SORT_KEY.
    They should also provide get_async_expr, get_interval,
    get_offset & set_offset (deprecated), is_on_sequence,
    get_nearest_prev_point, get_next_point,
    get_next_point_on_sequence, get_first_point
    get_start_point, and get_stop_point.

    They should also provide a self.__eq__ implementation
    which should return whether a SequenceBase-derived object
    is equal to another (represents the same set of points).

    """

    __slots__ = ()

    @property
    @abstractmethod
    def TYPE(self) -> str:
        """Cycling type of this sequence."""

    @property
    @abstractmethod
    def TYPE_SORT_KEY(self) -> int:
        """Used for comparison operations between different
        SequenceBase-derived class instances."""

    @classmethod
    @abstractmethod  # Note: stacked decorator not strictly enforced in Py2.x
    def get_async_expr(cls, start_point=0):
        """Express a one-off sequence at the initial cycle point."""
        pass

    @abstractmethod
    def __init__(self, sequence_string, context_start, context_stop=None):
        """Parse sequence string according to context point strings."""
        pass

    @abstractmethod
    def get_interval(self):
        """Return the cycling interval of this sequence."""
        pass

    @abstractmethod
    def get_offset(self):
        """Deprecated: return the offset used for this sequence."""
        pass

    @abstractmethod
    def set_offset(self, i_offset):
        """Deprecated: alter state to offset the entire sequence."""
        pass

    # NOTE: not using @abstractmethod because we need to
    # patch this method for caching purposes
    def is_on_sequence(self, point):
        """Is point on-sequence, disregarding bounds?"""
        raise NotImplementedError

    @abstractmethod
    def is_valid(self, point):
        """Is point on-sequence and in-bounds?"""
        pass

    @abstractmethod
    def get_prev_point(self, point):
        """Return the previous point < point, or None if out of bounds."""
        pass

    @abstractmethod
    def get_nearest_prev_point(self, point):
        """Return the largest point < some arbitrary point."""
        pass

    @abstractmethod
    def get_next_point(self, point):
        """Return the next point > point, or None if out of bounds."""
        pass

    @abstractmethod
    def get_next_point_on_sequence(self, point):
        """Return the next point > point assuming that point is on-sequence,
        or None if out of bounds."""
        pass

    @abstractmethod
    def get_first_point(self, point):
        """Return the first point >= to point, or None if out of bounds."""
        pass

    @abstractmethod
    def get_start_point(self):
        """Return the first point of this sequence."""
        pass

    @abstractmethod
    def get_stop_point(self):
        """Return the last point of this sequence, or None if unbounded."""
        pass

    @abstractmethod
    def __eq__(self, other) -> bool:
        # Return True if other (sequence) is equal to self.
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass


class ExclusionBase(metaclass=ABCMeta):
    """A collection of points or sequences that are treated in an
    exclusionary manner"""
    __slots__ = ('exclusion_sequences', 'exclusion_points',
                 'exclusion_start_point', 'exclusion_end_point')

    def __init__(self, start_point, end_point=None):
        """creates an exclusions object that can contain integer points
        or integer sequences to be used as excluded points."""
        self.exclusion_sequences = []
        self.exclusion_points = []
        self.exclusion_start_point = start_point
        self.exclusion_end_point = end_point

    @abstractmethod
    def build_exclusions(self, excl_points):
        """Constructs the set of exclusion sequences or points"""
        pass

    def __contains__(self, point):
        """Return True if the provided point is in this exclusion.

        Args:
            point (PointBase): The cycle point to check.

        """
        if point in self.exclusion_points:
            return True
        if any(seq.is_valid(point) for seq in self.exclusion_sequences):
            return True
        return False

    def __getitem__(self, key):
        """Allows indexing of the exclusion object"""
        return self.exclusion_sequences[key]

    def __str__(self):
        returns = []
        for point in sorted(self.exclusion_points):
            returns.append(str(point))
        for sequence in self.exclusion_sequences:
            returns.append(str(sequence))
        ret = ','.join(returns)
        if ',' in ret:
            ret = '(' + ret + ')'
        return ret


def cmp(self, other):
    """Temporary replacement for the Python2 cmp function."""
    if self == other:
        return 0
    if self < other:
        return -1
    return 1
