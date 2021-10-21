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

"""A Cylc xtrigger function."""

from contextlib import suppress


def echo(*args, **kwargs):
    """Prints args to stdout and return success only if kwargs['succeed'] is True.

    This may be a useful aid to understanding how xtriggers work.

    Returns
        tuple: (True/False, kwargs)

    """
    print("echo: ARGS:", args)
    print("echo: KWARGS:", kwargs)
    result = False
    with suppress(KeyError):
        result = kwargs["succeed"] is True
    return result, kwargs
