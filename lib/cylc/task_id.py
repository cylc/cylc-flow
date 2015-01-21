#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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


class TaskID(object):
    """Task ID utilities."""

    DELIM = '.'
    NAME_RE = r"\w[\w\-+%@]*"
    NAME_REC = re.compile(r"\A" + NAME_RE + r"\Z")
    POINT_RE = r"\S+"
    POINT_REC = re.compile(r"\A" + POINT_RE + r"\Z")
    SYNTAX = 'NAME' + DELIM + 'CYCLE_POINT'
    SYNTAX_OPT_POINT = 'NAME[' + DELIM + 'CYCLE_POINT]'

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
        """Return whether a task id is valid."""
        if not cls.DELIM in id_str:
            return False
        name, point = cls.split(id_str)
        # N.B. only basic cycle point check
        return (name and cls.NAME_REC.match(name) and
                point and cls.POINT_REC.match(point))
