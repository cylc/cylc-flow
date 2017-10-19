#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Port scan utilities."""

from multiprocessing import cpu_count, Process, Pipe
import sys
from time import sleep, time
import traceback
from uuid import uuid4

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.network.httpclient import (
    SuiteRuntimeServiceClient, ClientError, ClientTimeout)
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.suite_host import is_remote_host, get_host_ip_by_name

CONNECT_TIMEOUT = 5.0
INACTIVITY_TIMEOUT = 10.0
MSG_QUIT = "QUIT"
MSG_TIMEOUT = "TIMEOUT"
SLEEP_INTERVAL = 0.01


def _scan_worker(conn, timeout, my_uuid):
    """Port scan worker."""
    srv_files_mgr = SuiteSrvFilesManager()
    while True:
        try:
            if not conn.poll(SLEEP_INTERVAL):
                continue
            item = conn.recv()
            if item == MSG_QUIT:
                break
            conn.send(_scan_item(timeout, my_uuid, srv_files_mgr, item))
        except KeyboardInterrupt:
            break
    conn.close()


def _scan_item(timeout, my_uuid, srv_files_mgr, item):
    """Connect to item host:port (item) to get suite identify."""
    host, port = item
    host_anon = host
    if is_remote_host(host):
        host_anon = get_host_ip_by_name(host)  # IP reduces DNS traffic
    client = SuiteRuntimeServiceClient(
        None, host=host_anon, port=port, my_uuid=my_uuid,
        timeout=timeout, auth=SuiteRuntimeServiceClient.ANON_AUTH)
    try:
        result = client.identify()
    except ClientTimeout:
        return (host, port, MSG_TIMEOUT)
    except ClientError:
        return (host, port, None)
    else:
        owner = result.get('owner')
        name = result.get('name')
        states = result.get('states', None)
        if cylc.flags.debug:
            sys.stderr.write('   suite: %s %s\n' % (name, owner))
        if states is None:
            # This suite keeps its state info private.
            # Try again with the passphrase if I have it.
            try:
                pphrase = srv_files_mgr.get_auth_item(
                    srv_files_mgr.FILE_BASE_PASSPHRASE,
                    name, owner, host, content=True)
            except SuiteServiceFileError:
                pass
            else:
                if pphrase:
                    client.suite = name
                    client.owner = owner
                    client.host = host
                    client.auth = None
                    try:
                        result = client.identify()
                    except ClientError:
                        # Nope (private suite, wrong passphrase).
                        if cylc.flags.debug:
                            sys.stderr.write('    (wrong passphrase)\n')
                    else:
                        if cylc.flags.debug:
                            sys.stderr.write(
                                '    (got states with passphrase)\n')
        return (host, port, result)


def scan_many(items=None, timeout=None, updater=None):
    """Call "identify" method of suites on many host:port.

    Args:
        items (list): list of 'host' string or ('host', port) tuple to scan.
        timeout (float): connection timeout, default is CONNECT_TIMEOUT.
        updater (object): quit scan cleanly if updater.quit is set.

    Return:
        list: [(host, port, identify_result), ...]
    """
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = CONNECT_TIMEOUT
    my_uuid = uuid4()
    # Determine hosts to scan
    if not items:
        items = GLOBAL_CFG.get(["suite host scanning", "hosts"])
    # Ensure that it does "localhost" only once
    items = set(items)
    for item in list(items):
        if not isinstance(item, tuple) and not is_remote_host(item):
            items.remove(item)
            items.add("localhost")
    # To do and wait (submitted, waiting for results) sets
    todo_set = set()
    wait_set = set()
    # Determine ports to scan
    base_port = None
    max_ports = None
    for item in items:
        if isinstance(item, tuple):
            # Assume item is ("host", port)
            todo_set.add(item)
        else:
            # Full port range for a host
            if base_port is None or max_ports is None:
                base_port = GLOBAL_CFG.get(['communication', 'base port'])
                max_ports = GLOBAL_CFG.get(
                    ['communication', 'maximum number of ports'])
            for port in range(base_port, base_port + max_ports):
                todo_set.add((item, port))
    proc_items = []
    results = []
    # Number of child processes
    max_procs = GLOBAL_CFG.get(["process pool size"])
    if max_procs is None:
        max_procs = cpu_count()
    try:
        while todo_set or proc_items:
            no_action = True
            # Get results back from child processes where possible
            busy_proc_items = []
            while proc_items:
                if updater and updater.quit:
                    raise KeyboardInterrupt()
                proc, my_conn, terminate_time = proc_items.pop()
                if my_conn.poll():
                    host, port, result = my_conn.recv()
                    if result is None:
                        # Can't connect, ignore
                        wait_set.remove((host, port))
                    elif result == MSG_TIMEOUT:
                        # Connection timeout, leave in "wait_set"
                        pass
                    else:
                        # Connection success
                        results.append((host, port, result))
                        wait_set.remove((host, port))
                    if todo_set:
                        # Immediately give the child process something to do
                        host, port = todo_set.pop()
                        wait_set.add((host, port))
                        my_conn.send((host, port))
                        busy_proc_items.append(
                            (proc, my_conn, time() + INACTIVITY_TIMEOUT))
                    else:
                        # Or quit if there is nothing left to do
                        my_conn.send(MSG_QUIT)
                        my_conn.close()
                        proc.join()
                    no_action = False
                elif time() > terminate_time:
                    # Terminate child process if it is taking too long
                    proc.terminate()
                    proc.join()
                    no_action = False
                else:
                    busy_proc_items.append((proc, my_conn, terminate_time))
            proc_items += busy_proc_items
            # Create some child processes where necessary
            while len(proc_items) < max_procs and todo_set:
                if updater and updater.quit:
                    raise KeyboardInterrupt()
                my_conn, conn = Pipe()
                try:
                    proc = Process(
                        target=_scan_worker, args=(conn, timeout, my_uuid))
                except OSError:
                    # Die if unable to start any worker process.
                    # OK to wait and see if any worker process already running.
                    if not proc_items:
                        raise
                    if cylc.flags.debug:
                        traceback.print_exc()
                else:
                    proc.start()
                    host, port = todo_set.pop()
                    wait_set.add((host, port))
                    my_conn.send((host, port))
                    proc_items.append(
                        (proc, my_conn, time() + INACTIVITY_TIMEOUT))
                    no_action = False
            if no_action:
                sleep(SLEEP_INTERVAL)
    except KeyboardInterrupt:
        return []
    # Report host:port with no results
    if wait_set:
        sys.stderr.write(
            'WARNING, scan timed out, no result for the following:\n')
        for key in sorted(wait_set):
            sys.stderr.write('  %s:%s\n' % key)
    return results
