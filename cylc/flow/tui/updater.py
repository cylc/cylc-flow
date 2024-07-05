#!/usr/bin/env python3
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

"""Contains the logic for updating the Tui app."""

from asyncio import (
    run,
    sleep,
    gather,
)
from contextlib import suppress
from copy import deepcopy
from getpass import getuser
from multiprocessing import Queue
from time import time

from zmq.error import ZMQError

from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    CylcError,
    WorkflowStopped,
)
from cylc.flow.id import Tokens
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.scan import (
    filter_name,
    graphql_query,
    is_active,
    scan,
)
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
)
from cylc.flow.tui.data import (
    QUERY
)
from cylc.flow.tui.util import (
    compute_tree,
    suppress_logging,
)
from cylc.flow.workflow_status import (
    WorkflowStatus,
)


ME = getuser()


def get_default_filters():
    """Return default task/workflow filters.

    These filters show everything.
    """
    return {
        # filtered task statuses
        'tasks': dict.fromkeys(TASK_STATUSES_ORDERED, True),
        'workflows': {
            # filtered workflow statuses
            **{
                state.value: True
                for state in WorkflowStatus
            },
            # filtered workflow ids
            'id': '.*',
        }
    }


def set_message(data, workflow_id, message, prefix='Error - '):
    """Set a message to display instead of the workflow contents.

    This is for critical errors that mean we are unable to load a workflow.

    Args:
        data:
            The updater data.
        workflow_id:
            The ID of the workflow to set the error for.
        message:
            A message string or an Exception instance to use for the error
            text. If a string is provided, it may not contain newlines.
        prefix:
            A string that will be prepended to the message.

    """
    if isinstance(message, Exception):
        # use the first line of the error message.
        message = str(message).splitlines()[0]
    for workflow in data['workflows']:
        # find the workflow in the data
        if workflow['id'] == workflow_id:
            # use the _tui_data field to hold the message
            workflow['_tui_data'] = (
                f'{prefix}{message}'
            )
            break


class Updater():
    """The bit of Tui which provides the data.

    It lists workflows using the "scan" interface, and provides detail using
    the "GraphQL" interface.

    """

    # the interval between workflow listing scans
    BASE_SCAN_INTERVAL = 20

    # the interval between workflow data updates
    BASE_UPDATE_INTERVAL = 1

    # the command signal used to tell the updater to shut down
    SIGNAL_TERMINATE = 'terminate'

    def __init__(self, client_timeout=3):
        # Cylc comms clients for each workflow we're connected to
        self._clients = {}

        # iterate over this to get a list of workflows
        self._scan_pipe = None
        # the new pipe if the workflow filter options are changed
        self.__scan_pipe = None

        # task/workflow filters
        self.filters = None  # note set on self.run()
        # queue for pushing out updates
        self.update_queue = Queue(
            # block the updater if it gets too far ahead of the application
            maxsize=10
        )
        # queue for commands to the updater
        self._command_queue = Queue()

        # the maximum time to wait for a workflow update
        self.client_timeout = client_timeout

    def subscribe(self, w_id):
        """Subscribe to updates from a workflow."""
        self._command_queue.put((self._subscribe.__name__, w_id))

    def unsubscribe(self, w_id):
        """Unsubscribe to updates from a workflow."""
        self._command_queue.put((self._unsubscribe.__name__, w_id))

    def update_filters(self, filters):
        """Update the task state filter."""
        self._command_queue.put((self._update_filters.__name__, filters))

    def terminate(self):
        """Stop the updater."""
        self._command_queue.put((self.SIGNAL_TERMINATE, None))

    def start(self, filters):
        """Start the updater in a new asyncio.loop.

        The Tui app will call this within a dedicated process.
        """
        with suppress(KeyboardInterrupt):
            run(self.run(filters))

    async def run(self, filters):
        """Start the updater in an existing asyncio.loop.

        The tests call this within the same process.
        """
        with suppress_logging():
            self._update_filters(filters)
            while True:
                ret = await self._update()
                if ret == self.SIGNAL_TERMINATE:
                    break
                self.update_queue.put(ret)

    def _subscribe(self, w_id):
        if w_id not in self._clients:
            self._clients[w_id] = None

    def _unsubscribe(self, w_id):
        if w_id in self._clients:
            self._clients.pop(w_id)

    def _update_filters(self, filters):
        if (
            not self.filters
            or filters['workflows']['id'] != self.filters['workflows']['id']
        ):
            # update the scan pipe
            self.__scan_pipe = (
                # scan all workflows
                scan
                | filter_name(filters['workflows']['id'])
                # if the workflow is active, retrieve its status
                | is_active(True, filter_stop=False)
                | graphql_query({'status': None})
            )

        self.filters = filters

    async def _update(self):
        """Run one iteration of the updater.

        Either returns the next update or "self.SIGNAL_TERMINATE".
        """
        last_scan_time = 0
        # process any pending commands
        while not self._command_queue.empty():
            (command, payload) = self._command_queue.get()
            if command == self.SIGNAL_TERMINATE:
                return command
            getattr(self, command)(payload)

        # do a workflow scan if it's due
        update_start_time = time()
        if update_start_time - last_scan_time > self.BASE_SCAN_INTERVAL:
            data = await self._scan()

        # get the next snapshot from workflows we are subscribed to
        update = await self._run_update(data)

        # schedule the next update
        update_time = time() - update_start_time
        await sleep(self.BASE_UPDATE_INTERVAL - update_time)
        return update

    async def _run_update(self, data):
        # copy the scanned data so it can be reused for future updates
        data = deepcopy(data)

        # connect to schedulers if needed
        self._connect(data)

        # update data with the response from each workflow
        # NOTE: Currently we're bunching these updates together so Tui will
        #       only update as fast as the slowest responding workflow.
        #       We could run these updates separately if this is an issue.
        await gather(
            *(
                self._update_workflow(w_id, client, data)
                for w_id, client in self._clients.items()
            )
        )

        return compute_tree(data)

    async def _update_workflow(self, w_id, client, data):
        if not client:
            # we could not connect to this workflow
            # e.g. workflow is shut down
            return

        try:
            # fetch the data from the workflow
            workflow_update = await client.async_request(
                'graphql',
                {
                    'request_string': QUERY,
                    'variables': {
                        # list of task states we want to see
                        'taskStates': [
                            state
                            for state, is_on in self.filters['tasks'].items()
                            if is_on
                        ]
                    }
                }
            )
        except WorkflowStopped:
            # remove the client on any error, we'll reconnect next time
            self._clients[w_id] = None
            for workflow in data['workflows']:
                if workflow['id'] == w_id:
                    break
            else:
                # there's no entry here, create a stub
                # NOTE: this handles the situation where we've connected to a
                # workflow before it has appeared in a scan which matters to
                # the tests as they use fine timings
                data['workflows'].append({
                    'id': w_id,
                    'status': 'stopped',
                })
        except ClientTimeout:
            self._clients[w_id] = None
            set_message(
                data,
                w_id,
                'Timeout communicating with workflow.'
                ' Use "--comms-timeout" to increase the timeout',
            )
        except (CylcError, ZMQError) as exc:
            # something went wrong :(
            # remove the client on any error, we'll reconnect next time
            self._clients[w_id] = None
            set_message(data, w_id, exc)
        else:
            # the data arrived, add it to the update
            workflow_data = workflow_update['workflows'][0]
            for workflow in data['workflows']:
                if workflow['id'] == workflow_data['id']:
                    workflow.update(workflow_data)
                    break

    def _connect(self, data):
        """Connect to all subscribed workflows."""
        for w_id, client in self._clients.items():
            if not client:
                try:
                    self._clients[w_id] = get_client(
                        Tokens(w_id)['workflow'],
                        timeout=self.client_timeout,
                    )
                except WorkflowStopped:
                    set_message(
                        data, w_id, 'Workflow is not running', prefix=''
                    )
                except ClientTimeout:
                    set_message(
                        data,
                        w_id,
                        'Timeout connecting to workflow.'
                        ' Use "--comms-timeout" to increase the timeout',
                    )
                except (ZMQError, ClientError) as exc:
                    set_message(data, w_id, exc)

    async def _scan(self):
        """Scan for workflows on the filesystem."""
        data = {'workflows': []}
        workflow_filter_statuses = {
            status
            for status, filtered in self.filters['workflows'].items()
            if filtered
        }
        if self.__scan_pipe:
            # switch to the new pipe if it has been changed
            self._scan_pipe = self.__scan_pipe
        async for workflow in self._scan_pipe:
            status = workflow.get('status', WorkflowStatus.STOPPED.value)
            if status not in workflow_filter_statuses:
                # this workflow is filtered out
                continue
            data['workflows'].append({
                'id': f'~{ME}/{workflow["name"]}',
                'name': workflow['name'],
                'status': status,
                'stateTotals': {},
            })

        data['workflows'].sort(key=lambda x: x['id'])
        return data
