#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Unicode utility."""


def utf8_enforce(data):
    """Recursively enforce UTF-8 encoding for Unicode strings."""
    if isinstance(data, unicode):
        return data.encode('utf-8')
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_dict.update(
                {utf8_enforce(key): utf8_enforce(value)}
            )
        return new_dict
    if isinstance(data, list):
        return [utf8_enforce(item) for item in data]
    return data
