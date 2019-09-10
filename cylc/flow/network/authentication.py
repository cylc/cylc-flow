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

from cylc.flow.suite_srv_files_mgr import SuiteSrvFilesManager


def get_secret(suite):
    """Return the secret used for encrypting messages.

    Currently this is the suite passphrase. This means we are sending
    many messages all encrypted with the same hash which isn't great.

    TODO: Upgrade the secret to add foreword security.

    """
    return get_auth_item(
        SuiteFiles.Service.PASSPHRASE,
        suite, content=True
    )


def decrypt(message, secret):
    """Make a message readable.

    Args:
        message (str): The message to decode - str.
        secret (str): The decrypt key.

    Return:
        dict - The received message plus a `user` field.

    """
    # TODO
    return {"message":"PASS", "user": "ANON"}


def encrypt(message, secret):
    """Make a message unreadable.

    Args:
        message (dict): The message to send, must be serializable .
        secret (str): The encrypt key.

    Return:
        str

    """
    # TODO
    return "PASS"


# Note on TODOs: at this state, can run a suite fine, but the jobs will hang in
# submitted state etc. & will give the error message (see job.err) of:
#
#  "ClientTimeout: Timeout waiting for server response."
#
# & the same error message is returned on attempt to 'cylc stop <suite>'.
#
# The suite log will show, e.g:
#
# ...
#2019-09-10T22:20:16+01:00 INFO - [hello.20190910T2320+01] -triggered off []
# Exception in thread Thread-1:
# Traceback (most recent call last):
#   File "/home/h06/sbarth/miniconda3/lib/python3.7/threading.py", line 917, in _bootstrap_inner
#    self.run()
#  File "/home/h06/sbarth/miniconda3/lib/python3.7/threading.py", line 865, in run
#    self._target(*self._args, **self._kwargs)
#  File "/net/home/h06/sbarth/cylc.git/cylc/flow/network/server.py", line 177, in _listener
#    if message['command'] in PB_METHOD_MAP:
#KeyError: 'command'
# [0m
# [0m2019-09-10T22:20:18+01:00 INFO - [hello.20190910T2320+01] status=ready: ...
#
