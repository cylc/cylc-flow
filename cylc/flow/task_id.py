# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Task ID utilities."""


import re

from cylc.flow.cycling.loader import get_point, standardise_point_string
from cylc.flow.exceptions import PointParsingError


SEP_PATTERN = r'[^\.\:\#\/]+'

TASK_GLOB_DOT = re.compile(
    rf'''
        ^
        (?P<namespace>{SEP_PATTERN})
        (?:\.(?P<point>{SEP_PATTERN}))?
        (?:\:(?P<state>{SEP_PATTERN}))?
        (?:\#(?P<job>{SEP_PATTERN}))?
        $
    ''',
    re.X
)
TASK_GLOB_PATH = re.compile(
    rf'''
        ^
        (?P<point>{SEP_PATTERN})
        \/
        (?P<namespace>{SEP_PATTERN})
        (?:\:(?P<state>{SEP_PATTERN}))?
        (?:\#(?P<job>{SEP_PATTERN}))?
        $
    ''',
    re.X
)


def parse_reference(string):
    """Parse a cycle/namespace/state/job reference string.

    Supports both formats:

    * namespace[.cycle][:status][#job]
    * cycle[/namespace][:status][#job]

    Returns:
        dict - Dictionary containing the keys:

        * point
        * namespace
        * state
        * job

    """
    match = TASK_GLOB_DOT.match(string)
    if match:
        return match.groupdict()
    match = TASK_GLOB_PATH.match(string)
    if match:
        return match.groupdict()


class TaskID:
    """Task ID utilities."""

    DELIM = '.'
    DELIM_RE = r"\."
    DELIM2 = '/'
    NAME_SUFFIX_RE = r"[\w\-+%@]+"
    NAME_SUFFIX_REC = re.compile(r"\A" + NAME_SUFFIX_RE + r"\Z")
    NAME_RE = r"\w[\w\-+%@]*"
    NAME_REC = re.compile(r"\A" + NAME_RE + r"\Z")
    POINT_RE = r"\S+"
    POINT_REC = re.compile(r"\A" + POINT_RE + r"\Z")
    SYNTAX = 'NAME' + DELIM + 'CYCLE_POINT'
    SYNTAX_OPT_POINT = 'NAME[' + DELIM + 'CYCLE_POINT]'
    ID_RE = NAME_RE + DELIM_RE + POINT_RE

    @classmethod
    def get(cls, name, point):
        """Return a task id from name and a point string."""
        return name + cls.DELIM + str(point)

    @classmethod
    def split(cls, id_str):
        """Return a name and a point string from an id."""
        return id_str.split(cls.DELIM, 1)

    @classmethod
    def is_valid_name(cls, name):
        """Return whether a task name is valid."""
        return name and cls.NAME_REC.match(name)

    @classmethod
    def is_valid_id(cls, id_str):
        """Return whether a task id is valid "NAME.POINT" format."""
        if cls.DELIM not in id_str:
            return False
        name, point = cls.split(id_str)
        # N.B. only basic cycle point check
        return (name and cls.NAME_REC.match(name) and
                point and cls.POINT_REC.match(point))

    @classmethod
    def is_valid_id_2(cls, id_str):
        """Return whether id_str is good as a client argument for e.g. insert.

        Return True if "." or "/" appears once in the string. Cannot really
        do more as the string may have wildcards.
        """
        return id_str.count(cls.DELIM) == 1 or id_str.count(cls.DELIM2) == 1

    @classmethod
    def get_standardised_point_string(cls, point_string):
        """Return a standardised point string.

        Used to process incoming command arguments.
        """
        try:
            point_string = standardise_point_string(point_string)
        except PointParsingError as exc:
            # (This is only needed to raise a clearer error message).
            raise ValueError(
                "Invalid cycle point: %s (%s)" % (point_string, exc))
        return point_string

    @classmethod
    def get_standardised_point(cls, point_string):
        """Return a standardised point."""
        return get_point(cls.get_standardised_point_string(point_string))

    @classmethod
    def get_standardised_taskid(cls, task_id):
        """Return task ID with standardised cycle point."""
        name, point_string = cls.split(task_id)
        return cls.get(
            name, cls.get_standardised_point_string(point_string))
