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
"""Network authorisation layer."""

from enum import IntEnum
from functools import wraps

from cylc.flow import LOG


class Priv(IntEnum):
    """Cylc privilege levels.

    In Cylc configurations use the lower-case form of each privilege level
    e.g. ``control`` for ``Priv.CONTROL``.

    These levels are ordered (by the integer associated with each) from 0.
    Each privilege level grants access to the levels below it.

    """

    CONTROL = 6
    """Provides full control of a suite."""

    SHUTDOWN = 5  # (Not used yet - for the post-passphrase era.)
    """Allows issuing of the shutdown command."""

    READ = 4
    """Permits read access to the suite's state."""

    STATE_TOTALS = 3
    """Provides access to the count of tasks in each state."""

    DESCRIPTION = 2
    """Permits reading of suite metadata."""

    IDENTITY = 1
    """Provides read access to the suite name, owner and Cylc version."""

    NONE = 0
    """No access."""

    @classmethod
    def parse(cls, key):
        """Obtain a privilege enumeration from a string."""
        return cls.__members__[key.upper().replace('-', '_')]


def authorise(req_priv_level):
    """Add authorisation to an endpoint.

    This decorator extracts the `user` field from the incoming message to
    determine the client's privilege level.

    Args:
        req_priv_level (cylc.flow.network.Priv): A privilege level for the
            method.

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
        def _authorise(self, *args, user='?', meta=None, **kwargs):
            if not meta:
                meta = {}
            host = meta.get('host', '?')
            prog = meta.get('prog', '?')

            usr_priv_level = self._get_priv_level(user)
            if usr_priv_level < req_priv_level:
                LOG.warn(
                    "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s",
                    usr_priv_level, req_priv_level, user, host, prog)
                raise Exception('Authorisation failure')
            LOG.info(
                '[client-command] %s %s@%s:%s', fcn.__name__, user, host, prog)
            return fcn(self, *args, **kwargs)

        # add authorisation level to docstring
        _authorise.__doc__ += (
            f'Authentication:\n{" " * 12}'
            f':py:obj:`{__loader__.name}.{str(req_priv_level)}`\n'
        )
        return _authorise
    return wrapper
