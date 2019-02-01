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


# Dummy passphrase for client access from users without the suite passphrase.
NO_PASSPHRASE = 'the quick brown fox'


class Priv(IntEnum):
    CONTROL = 6
    SHUTDOWN = 5  # (Not used yet - for the post-passphrase era.)
    READ = 4
    STATE_TOTALS = 3
    DESCRIPTION = 2
    IDENTITY = 1
    NONE = 0

    @classmethod
    def parse(cls, key):
        return cls.__members__[key]


HASH = 'HS256'


def get_secret(suite):
    """Return the secret used for encrypting messages - i.e. the passphrase"""
    return SuiteSrvFilesManager().get_auth_item(
        SuiteSrvFilesManager.FILE_BASE_PASSPHRASE,
        suite
    )


def decrypt(message, secret):
    message = jwt.decode(message, secret, algorithms=[HASH])
    # if able to decode assume this is the user
    message['user'] = getpass.getuser()
    return message


def encrypt(message, secret):
    return jwt.encode(message, secret, algorithm=HASH)
