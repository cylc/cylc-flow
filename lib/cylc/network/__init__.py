#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

"""Package for network interfaces to cylc suite server objects."""

from enum import IntEnum
import getpass

from jose import jwt

from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


HASH = 'HS256'  # Encoding for JWT


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


def get_secret(suite):
    """Return the secret used for encrypting messages.

    Currently this is the suite passphrase. This means we are sending
    many messages all encrypted with the same hash which isn't great.

    TODO: Upgrade the secret to add foreword security.

    """
    return SuiteSrvFilesManager().get_auth_item(
        SuiteSrvFilesManager.FILE_BASE_PASSPHRASE,
        suite, content=True
    )


def decrypt(message, secret):
    """Make a message readable.

    Args:
        message (str): The message to decode - JWT str.
        secret (str): The decrypt key.

    Return:
        dict - The received message plus a `user` field.

    """
    message = jwt.decode(message, secret, algorithms=[HASH])
    # if able to decode assume this is the user
    message['user'] = getpass.getuser()
    return message


def encrypt(message, secret):
    """Make a message unreadable.

    Args:
        message (dict): The message to send, must be serialiseable .
        secret (str): The encrypt key.

    Return:
        str - JWT str.

    """
    return jwt.encode(message, secret, algorithm=HASH)
