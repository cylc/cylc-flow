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
from threading import Thread
from time import sleep

import zmq
import zmq.asyncio

from cylc.flow import LOG
from cylc.flow.exceptions import (
    ClientError,
    CylcError,
    CylcVersionError,
    ServiceFileError,
    WorkflowStopped
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.workflow_files import (
    ContactFileFields,
    KeyType,
    KeyOwner,
    KeyInfo,
    load_contact_file,
    get_workflow_srv_dir
)

API = 5  # cylc API version
MSG_TIMEOUT = "TIMEOUT"


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


def get_location(workflow: str):
    """Extract host and port from a workflow's contact file.

    NB: if it fails to load the workflow contact file, it will exit.

    Args:
        workflow (str): workflow name
    Returns:
        Tuple[str, int, int]: tuple with the host name and port numbers.
    Raises:
        ClientError: if the workflow is not running.
        CylcVersionError: if target is a Cylc 7 (or earlier) workflow.
    """
    try:
        contact = load_contact_file(workflow)
    except ServiceFileError:
        raise WorkflowStopped(workflow)

    host = contact[ContactFileFields.HOST]
    host = get_fqdn_by_host(host)
    port = int(contact[ContactFileFields.PORT])
    if ContactFileFields.PUBLISH_PORT in contact:
        pub_port = int(contact[ContactFileFields.PUBLISH_PORT])
    else:
        version = (
            contact['CYLC_VERSION'] if 'CYLC_VERSION' in contact else None)
        raise CylcVersionError(version=version)
    return host, port, pub_port


class ZMQSocketBase:
    """Initiate the ZMQ socket bind for specified pattern on new thread.

    NOTE: Security to be provided via zmq.auth (see PR #3359).

    Args:
        pattern (enum): ZeroMQ message pattern (zmq.PATTERN).

        context (object, optional): instantiated ZeroMQ context, defaults
            to zmq.asyncio.Context().

        barrier (object, optional): threading.Barrier object for syncing with
            other threads.

        threaded (bool, optional): Start socket on separate thread.

        daemon (bool, optional): daemonise socket thread.

    This class is designed to be inherited by REP Server (REQ/REP)
    and by PUB Publisher (PUB/SUB), as the start-up logic is similar.


    To tailor this class overwrite it's method on inheritance.

    """

    def __init__(self, pattern, workflow=None, bind=False, context=None,
                 barrier=None, threaded=False, daemon=False):
        self.bind = bind
        if context is None:
            self.context = zmq.asyncio.Context()
        else:
            self.context = context
        self.barrier = barrier
        self.pattern = pattern
        self.daemon = daemon
        self.workflow = workflow
        self.host = None
        self.port = None
        self.socket = None
        self.threaded = threaded
        self.thread = None
        self.loop = None
        self.stopping = False

    def start(self, *args, **kwargs):
        """Start the server/network-component.

        Pass arguments to _start_
        """
        if self.threaded:
            self.thread = Thread(
                target=self._start_sequence,
                args=args,
                kwargs=kwargs,
                daemon=self.daemon
            )
            self.thread.start()
        else:
            self._start_sequence(*args, **kwargs)

    def _start_sequence(self, *args, **kwargs):
        """Create the thread async loop, and bind socket."""
        # set asyncio loop on thread
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
        except (ValueError):
            raise ServiceFileError(
                f"Failed to find server's public "
                f"key in "
                f"{srv_prv_key_info.full_key_path}."
            )
        except(OSError):
            raise ServiceFileError(
                f"IO error opening server's private "
                f"key from "
                f"{srv_prv_key_info.full_key_path}."
            )
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
            raise CylcError(f'could not start Cylc ZMQ server: {exc}')

        if self.barrier is not None:
            self.barrier.wait()

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
        except (OSError, ValueError):
            raise ClientError(error_msg)
        if client_priv_key is None:  # this can't be caught by exception
            raise ClientError(error_msg)
        self.socket.curve_publickey = client_public_key
        self.socket.curve_secretkey = client_priv_key

        # A client can only connect to the server if it knows its public key,
        # so we grab this from the location it was created on the filesystem:
        try:
            # 'load_certificate' will try to load both public & private keys
            # from a provided file but will return None, not throw an error,
            # for the latter item if not there (as for all public key files)
            # so it is OK to use; there is no method to load only the
            # public key.
            server_public_key = zmq.auth.load_certificate(
                srv_pub_key_info.full_key_path)[0]
            self.socket.curve_serverkey = server_public_key
        except (OSError, ValueError):  # ValueError raised w/ no public key
            raise ClientError(
                "Failed to load the workflow's public key, so cannot connect.")

        self.socket.connect(f'tcp://{host}:{port}')

    def _socket_options(self):
        """Set socket options.

        i.e. self.socket.sndhwm
        """
        self.socket.sndhwm = 10000

    def _bespoke_start(self):
        """Initiate bespoke items on thread at start."""
        self.stopping = False
        sleep(0)  # yield control to other threads

    def stop(self, stop_loop=True):
        """Stop the server.

        Args:
            stop_loop (Boolean): Stop running IOLoop of current thread.

        """
        self._bespoke_stop()
        if stop_loop and self.loop and self.loop.is_running():
            self.loop.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join()  # Wait for processes to return
        if self.socket and not self.socket.closed:
            self.socket.close()
        LOG.debug('...stopped')

    def _bespoke_stop(self):
        """Bespoke stop items."""
        LOG.debug('stopping zmq socket...')
        self.stopping = True
