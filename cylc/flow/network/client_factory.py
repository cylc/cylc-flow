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

import os
from enum import Enum


class CommsMeth(Enum):
    """Used for identifying communication methods"""

    SSH = 'ssh'
    ZMQ = 'zmq'


def get_comms_method():
    """"Return Communication Method"""
    return os.getenv('CYLC_TASK_COMMS_METHOD', CommsMeth.ZMQ)


def get_runtime_client(comms_method, suite, comms_timeout=None):
    """Return import command for correct client"""
    if comms_method == CommsMeth.SSH:
        from cylc.flow.network.ssh_client import SuiteRuntimeClient
    else:
        from cylc.flow.network.client import SuiteRuntimeClient
    return SuiteRuntimeClient(suite, timeout=comms_timeout)


def get_client(suite, timeout=None):
    comms_method = get_comms_method()
    return get_runtime_client(comms_method, suite, comms_timeout=timeout)
