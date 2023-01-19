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

from enum import Enum
import os
from typing import TYPE_CHECKING, Union

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import ClientError

if TYPE_CHECKING:
    from cylc.flow.network.client import WorkflowRuntimeClientBase


class CommsMeth(Enum):
    """String literals used for identifying communication methods"""

    POLL = 'poll'
    SSH = 'ssh'
    ZMQ = 'zmq'
    HTTPS = 'https'


class LocalCommsMeth(Enum):
    """String literals used for identifying CLI communication methods"""

    ZMQ = 'zmq'
    HTTPS = 'https'


def get_comms_method(comms_method: Union[str, None] = None) -> CommsMeth:
    """"Return Communication Method from environment variable, default zmq"""
    if comms_method is None:
        comms_method = os.getenv('CYLC_TASK_COMMS_METHOD')
        # separate to avoid extra config file read
        if comms_method is None:
            comms_method = glbl_cfg().get(
                ['platforms', 'localhost', 'communication method']
            )
    return CommsMeth(comms_method)


def get_runtime_client(
    comms_method: CommsMeth,
    workflow: str,
    timeout: Union[float, str, None] = None
) -> 'WorkflowRuntimeClientBase':
    """Return client for the provided communication method.

        Args:
            comm_method: communication method
            workflow: workflow name
    """
    if comms_method == CommsMeth.SSH:
        from cylc.flow.network.ssh_client import WorkflowRuntimeClient
    elif comms_method == CommsMeth.HTTPS:
        try:
            from cylc.uiserver.client import (  # type: ignore[no-redef]
                WorkflowRuntimeClient
            )
        except ImportError as exc:
            raise ClientError(
                'HTTPS comms method requires UI Server installation',
                f'{exc}'
            )
    else:
        from cylc.flow.network.client import (  # type: ignore[no-redef]
            WorkflowRuntimeClient
        )
    return WorkflowRuntimeClient(workflow, timeout=timeout)


def get_client(workflow, timeout=None, method=None):
    """Get communication method and return correct WorkflowRuntimeClient"""
    return get_runtime_client(
        get_comms_method(method),
        workflow,
        timeout=timeout
    )
