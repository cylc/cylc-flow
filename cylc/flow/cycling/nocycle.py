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

"""
Cycling logic for isolated non-cycling startup and shutdown graphs.
"""

from cylc.flow.cycling import PointBase, SequenceBase

# cycle point values
NOCYCLE_PT_STARTUP = "startup"
NOCYCLE_PT_SHUTDOWN = "shutdown"

NOCYCLE_POINTS = (
    NOCYCLE_PT_STARTUP,
    NOCYCLE_PT_SHUTDOWN
)

CYCLER_TYPE_NOCYCLE = "nocycle"
CYCLER_TYPE_SORT_KEY_NOCYCLE = 1

# Unused abstract methods below left to raise NotImplementedError.


class NocyclePoint(PointBase):
    """A non-advancing string-valued cycle point."""

    TYPE = CYCLER_TYPE_NOCYCLE
    TYPE_SORT_KEY = CYCLER_TYPE_SORT_KEY_NOCYCLE

    __slots__ = ('value')

    def __init__(self, value: str) -> None:
        """Initialise a nocycle point.

        >>> NocyclePoint(NOCYCLE_PT_STARTUP)
        startup
        >>> NocyclePoint("beta")
        Traceback (most recent call last):
        ValueError: Illegal Nocycle value 'beta'
        """
        if value not in [NOCYCLE_PT_STARTUP, NOCYCLE_PT_SHUTDOWN]:
            raise ValueError(f"Illegal Nocycle value '{value}'")
        self.value = value

    def __hash__(self):
        """Hash it.

        >>> bool(hash(NocyclePoint(NOCYCLE_PT_STARTUP)))
        True
        """
        return hash(self.value)

    def __eq__(self, other):
        """Equality.

        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) ==
        ... NocyclePoint(NOCYCLE_PT_STARTUP))
        True
        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) ==
        ... NocyclePoint(NOCYCLE_PT_SHUTDOWN))
        False
        """
        return str(other) == str(self.value)

    def __le__(self, other):
        """Less than or equal (only if equal).

        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) <=
        ... NocyclePoint(NOCYCLE_PT_STARTUP))
        True
        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) <=
        ... NocyclePoint(NOCYCLE_PT_SHUTDOWN))
        False
        """
        return str(other) == self.value

    def __lt__(self, other):
        """Less than (never).

        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) <
        ... NocyclePoint(NOCYCLE_PT_STARTUP))
        False
        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) <
        ... NocyclePoint(NOCYCLE_PT_SHUTDOWN))
        False
        """
        return False

    def __gt__(self, other):
        """Greater than (never).
        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) >
        ... NocyclePoint(NOCYCLE_PT_STARTUP))
        False
        >>> (NocyclePoint(NOCYCLE_PT_STARTUP) >
        ... NocyclePoint(NOCYCLE_PT_SHUTDOWN))
        False
        """
        return False

    def __str__(self):
        """
        >>> str(NocyclePoint(NOCYCLE_PT_STARTUP))
        'startup'
        >>> str(NocyclePoint(NOCYCLE_PT_SHUTDOWN))
        'shutdown'
        """
        return self.value

    def _cmp(self, other):
        raise NotImplementedError

    def add(self, other):
        # Not used.
        raise NotImplementedError

    def sub(self, other):
        # Not used.
        raise NotImplementedError


class NocycleSequence(SequenceBase):
    """A single point sequence."""

    def __init__(self, dep_section, p_context_start=None, p_context_stop=None):
        """Workflow cycling context is ignored.

        >>> NocycleSequence("startup").point
        startup
        """
        self.point = NocyclePoint(dep_section)

    def __hash__(self):
        """Hash it.

        >>> bool(hash(NocycleSequence("startup")))
        True
        """
        return hash(str(self.point))

    def is_valid(self, point):
        """Is point on-sequence and in-bounds?

        >>> NocycleSequence("startup").is_valid("startup")
        True
        >>> NocycleSequence("startup").is_valid("shutdown")
        False
        """
        return str(point) == str(self.point)

    def get_first_point(self, point):
        """First point is the only point.

        >>> NocycleSequence("startup").get_first_point("shutdown")
        startup
        """
        return self.point

    def get_start_point(self, point):
        """First point is the only point."""
        # Not used.
        raise NotImplementedError
        return self.point

    def get_next_point(self, point):
        """There is no next point.

        >>> NocycleSequence("startup").get_next_point("startup")
        """
        return None

    def get_next_point_on_sequence(self, point):
        """There is no next point.

        >>> NocycleSequence("startup").get_next_point_on_sequence("startup")
        """
        return None

    def __eq__(self, other):
        """Equality.

        >>> NocycleSequence("startup") == NocycleSequence("startup")
        True
        >>> NocycleSequence("startup") == NocycleSequence("shutdown")
        False
        """
        try:
            return str(other.point) == str(self.point)
        except AttributeError:
            # (other has not .point)
            return False

    def __str__(self):
        """String.

        >>> str(NocycleSequence("startup"))
        'startup'
        """
        return str(self.point)

    def TYPE(self):
        raise NotImplementedError

    def TYPE_SORT_KEY(self):
        raise NotImplementedError

    def get_async_expr(cls, start_point=0):
        raise NotImplementedError

    def get_interval(self):
        """Return the cycling interval of this sequence."""
        raise NotImplementedError

    def get_offset(self):
        """Deprecated: return the offset used for this sequence."""
        raise NotImplementedError

    def set_offset(self, i_offset):
        """Deprecated: alter state to offset the entire sequence."""
        raise NotImplementedError

    def is_on_sequence(self, point):
        """Is point on-sequence, disregarding bounds?"""
        raise NotImplementedError

    def get_prev_point(self, point):
        """Return the previous point < point, or None if out of bounds."""
        raise NotImplementedError

    def get_nearest_prev_point(self, point):
        """Return the largest point < some arbitrary point."""
        raise NotImplementedError

    def get_stop_point(self):
        """Return the last point in this sequence, or None if unbounded."""
        raise NotImplementedError


NOCYCLE_SEQ_STARTUP = NocycleSequence(NOCYCLE_PT_STARTUP)
NOCYCLE_SEQ_SHUTDOWN = NocycleSequence(NOCYCLE_PT_SHUTDOWN)
