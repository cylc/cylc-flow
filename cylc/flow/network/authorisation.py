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
"""Network authorisation layer."""

from functools import wraps


def authorise():
    """Add authorisation to an endpoint.

    This decorator extracts the `user` field from the incoming message to
    determine the client's privilege level.

    Wrapped function args:
        user
            The authenticated user (determined server side)
        host
            The client host (if provided by client) - non trustworthy
        prog
            The client program name (if provided by client) - non trustworthy

    """
    def wrapper(fcn):
        @wraps(fcn)  # preserve args and docstrings
        def _call(self, *args, user='?', meta=None, **kwargs):
            if not meta:
                meta = {}
            return fcn(self, *args, meta=meta, **kwargs)

        return _call
    return wrapper
