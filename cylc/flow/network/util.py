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

"""Common networking utilities."""

import getpass
import json
from typing import Tuple

from cylc.flow.exceptions import (
    CylcVersionError,
    ServiceFileError,
    WorkflowStopped
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.workflow_files import (
    ContactFileFields,
    load_contact_file,
)


def encode_(message):
    """Convert the structure holding a message field from JSON to a string."""
    try:
        return json.dumps(message)
    except TypeError as exc:
        return json.dumps({'errors': [{'message': str(exc)}]})


def decode_(message):
    """Convert an encoded message string to JSON with an added 'user' field."""
    msg = json.loads(message)
    msg['user'] = getpass.getuser()  # assume this is the user
    return msg


def get_location(workflow: str) -> Tuple[str, int, int]:
    """Extract host and port from a workflow's contact file.

    NB: if it fails to load the workflow contact file, it will exit.

    Args:
        workflow: workflow ID
    Returns:
        Tuple (host name, port number, publish port number)
    Raises:
        WorkflowStopped: if the workflow is not running.
        CylcVersionError: if target is a Cylc 7 (or earlier) workflow.
    """
    try:
        contact = load_contact_file(workflow)
    except (IOError, ValueError, ServiceFileError):
        # Contact file does not exist or corrupted, workflow should be dead
        raise WorkflowStopped(workflow)

    host = contact[ContactFileFields.HOST]
    host = get_fqdn_by_host(host)
    port = int(contact[ContactFileFields.PORT])
    if ContactFileFields.PUBLISH_PORT in contact:
        pub_port = int(contact[ContactFileFields.PUBLISH_PORT])
    else:
        version = contact.get('CYLC_VERSION', None)
        raise CylcVersionError(version=version)
    return host, port, pub_port
