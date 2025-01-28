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
"""Package for network interfaces to Cylc scheduler objects."""

import asyncio
import getpass
import json
from typing import (
    TYPE_CHECKING,
    Optional,
    Tuple,
    Union,
)

import zmq
import zmq.asyncio
import zmq.auth

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ClientError,
    CylcError,
    CylcVersionError,
    ServiceFileError,
    WorkflowStopped,
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.workflow_files import (
    ContactFileFields,
    KeyInfo,
    KeyOwner,
    KeyType,
    get_workflow_srv_dir,
    load_contact_file,
)


if TYPE_CHECKING:
    # BACK COMPAT: typing_extensions.TypedDict
    # FROM: Python 3.7
    # TO: Python 3.11
    from typing_extensions import TypedDict


API = 5  # cylc API version
MSG_TIMEOUT = "TIMEOUT"

if TYPE_CHECKING:
    class ResponseDict(TypedDict, total=False):
        """Structure of server response messages.

        Confusingly, has similar format to GraphQL execution result.
        But if we change this now we could break compatibility for
        issuing commands to/receiving responses from workflows running in
        different versions of Cylc 8.
        """
        data: object
        """For most Cylc commands that issue GQL mutations, the data field will
        look like:
        data: {
        <mutationName1>: {
            result: [
            {
                id: <workflow/task ID>,
                response: [<success_bool>, <message>]
            },
            ...
            ]
        }
        }
        but this is not 100% consistent unfortunately
        """
        error: Union[Exception, str, dict]
        """If an error occurred that could not be handled.
        (usually a dict {message: str, traceback?: str}).
        """
        user: str
        cylc_version: str
        """Server (i.e. running workflow) Cylc version.

        Going forward, we include this so we can more easily handle any future
        back-compat issues."""


def load_server_response(message: str) -> 'ResponseDict':
    """Convert a JSON message string to dict with an added 'user' field."""
    msg = json.loads(message)
    if 'user' not in msg:
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
        raise WorkflowStopped(workflow) from None

    host = contact[ContactFileFields.HOST]
    host = get_fqdn_by_host(host)
    port = int(contact[ContactFileFields.PORT])
    if ContactFileFields.PUBLISH_PORT in contact:
        pub_port = int(contact[ContactFileFields.PUBLISH_PORT])
    else:
        version = contact.get('CYLC_VERSION', None)
        raise CylcVersionError(version=version)
    return host, port, pub_port


class ZMQSocketBase:
    """Initiate the ZMQ socket bind for specified pattern.

    NOTE: Security to be provided via zmq.auth (see PR #3359).

    Args:
        pattern (enum): ZeroMQ message pattern (zmq.PATTERN).

        context (object, optional): instantiated ZeroMQ context, defaults
            to zmq.asyncio.Context().

    This class is designed to be inherited by REP Server (REQ/REP)
    and by PUB Publisher (PUB/SUB), as the start-up logic is similar.


    To tailor this class overwrite it's method on inheritance.

    """

    def __init__(
        self,
        pattern,
        workflow: str,
        bind: bool = False,
        context: Optional[zmq.Context] = None,
    ):
        self.bind = bind
        if context is None:
            self.context: zmq.Context = zmq.asyncio.Context()
        else:
            self.context = context
        self.pattern = pattern
        self.workflow = workflow
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.socket: Optional[zmq.Socket] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stopping = False

    def start(self, *args, **kwargs):
        """Create the async loop, and bind socket."""
        # set asyncio loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        if self.bind:
            self._socket_bind(*args, **kwargs)
        else:
            self._socket_connect(*args, **kwargs)

        # initiate bespoke items
        self._bespoke_start()

    # Keeping srv_prv_key_loc as optional arg so as to not break interface
    def _socket_bind(self, min_port, max_port, srv_prv_key_loc=None):
        """Bind socket.

        Will use a port range provided to select random ports.

        """
        if srv_prv_key_loc is None:
            # Create new KeyInfo object for the server private key
            workflow_srv_dir = get_workflow_srv_dir(self.workflow)
            srv_prv_key_info = KeyInfo(
                KeyType.PRIVATE,
                KeyOwner.SERVER,
                workflow_srv_dir=workflow_srv_dir)
        else:
            srv_prv_key_info = KeyInfo(
                KeyType.PRIVATE,
                KeyOwner.SERVER,
                full_key_path=srv_prv_key_loc)

        # create socket
        self.socket = self.context.socket(self.pattern)
        self._socket_options()

        try:
            server_public_key, server_private_key = zmq.auth.load_certificate(
                srv_prv_key_info.full_key_path)
        except ValueError:
            raise ServiceFileError(
                "Failed to find server's public key in "
                f"{srv_prv_key_info.full_key_path}."
            ) from None
        except OSError as exc:
            raise ServiceFileError(
                "IO error opening server's private key from "
                f"{srv_prv_key_info.full_key_path}."
            ) from exc
        if server_private_key is None:  # this can't be caught by exception
            raise ServiceFileError(
                f"Failed to find server's private "
                f"key in "
                f"{srv_prv_key_info.full_key_path}."
            )
        self.socket.curve_publickey = server_public_key
        self.socket.curve_secretkey = server_private_key
        self.socket.curve_server = True

        try:
            if min_port == max_port:
                self.port = min_port
                self.socket.bind(f'tcp://*:{min_port}')
            else:
                self.port = self.socket.bind_to_random_port(
                    'tcp://*', min_port, max_port)
        except (zmq.error.ZMQError, zmq.error.ZMQBindError) as exc:
            raise CylcError(
                f'could not start Cylc ZMQ server: {exc}'
            ) from None

    # Keeping srv_public_key_loc as optional arg so as to not break interface
    def _socket_connect(self, host, port, srv_public_key_loc=None):
        """Connect socket to stub."""
        workflow_srv_dir = get_workflow_srv_dir(self.workflow)
        if srv_public_key_loc is None:
            # Create new KeyInfo object for the server public key
            srv_pub_key_info = KeyInfo(
                KeyType.PUBLIC,
                KeyOwner.SERVER,
                workflow_srv_dir=workflow_srv_dir)

        else:
            srv_pub_key_info = KeyInfo(
                KeyType.PUBLIC,
                KeyOwner.SERVER,
                full_key_path=srv_public_key_loc)

        self.host = host
        self.port = port
        self.socket = self.context.socket(self.pattern)
        self._socket_options()

        client_priv_key_info = KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.CLIENT,
            workflow_srv_dir=workflow_srv_dir)
        error_msg = "Failed to find user's private key, so cannot connect."
        try:
            client_public_key, client_priv_key = zmq.auth.load_certificate(
                client_priv_key_info.full_key_path)
        except ValueError:
            raise ClientError(error_msg) from None
        except OSError as exc:
            raise ClientError(error_msg) from exc
        if client_priv_key is None:  # this can't be caught by exception
            raise ClientError(error_msg)
        self.socket.curve_publickey = client_public_key
        self.socket.curve_secretkey = client_priv_key

        # A client can only connect to the server if it knows its public key,
        # so we grab this from the location it was created on the filesystem:
        error_msg = (
            "Failed to load the workflow's public key, so cannot connect."
        )
        try:
            # 'load_certificate' will try to load both public & private keys
            # from a provided file but will return None, not throw an error,
            # for the latter item if not there (as for all public key files)
            # so it is OK to use; there is no method to load only the
            # public key.
            server_public_key = zmq.auth.load_certificate(
                srv_pub_key_info.full_key_path)[0]
            self.socket.curve_serverkey = server_public_key
        except ValueError:  # ValueError raised w/ no public key
            raise ClientError(error_msg) from None
        except OSError as exc:
            raise ClientError(error_msg) from exc

        self.socket.connect(f'tcp://{host}:{port}')

    def _socket_options(self):
        """Set socket options.

        i.e. self.socket.sndhwm
        """
        self.socket.sndhwm = 10000

    def _bespoke_start(self):
        """Initiate bespoke items at start."""
        self.stopping = False

    def stop(self, stop_loop=True):
        """Stop the server.

        Args:
            stop_loop (Boolean): Stop running IOLoop.

        """
        self._bespoke_stop()
        if stop_loop and self.loop and self.loop.is_running():
            self.loop.stop()
        if self.socket and not self.socket.closed:
            self.socket.close()
        LOG.debug('...stopped')

    def _bespoke_stop(self):
        """Bespoke stop items."""
        LOG.debug('stopping zmq socket...')
        self.stopping = True
