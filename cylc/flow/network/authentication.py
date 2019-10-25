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
"""Network authentication layer."""

import getpass
import json

from cylc.flow.suite_files import UserFiles, get_auth_item


def get_client_private_key_location(suite):
    """ Return the secret used to encrypt messages sent by the client. """
    return get_auth_item(
        UserFiles.Auth.CLIENT_PRIVATE_KEY_CERTIFICATE, suite, content=False)


def decode_(message):
    """ Decode a message from a string to JSON, with an added 'user' field. """
    msg = json.loads(message)
    # if able to decode assume this is the user
    msg['user'] = getpass.getuser()
    return msg


def encode_(message):
    """ Encode a message from JSON format to a string. """
    return json.dumps(message)
