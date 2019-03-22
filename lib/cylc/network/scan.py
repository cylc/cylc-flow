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
"""Port scan utilities."""

import asyncio
import os
from pwd import getpwall
import re
import sys
import socket

from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.hostuserutil import is_remote_host, get_host_ip_by_name
from cylc.network.client import (
    SuiteRuntimeClient, ClientError, ClientTimeout)
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)

DEBUG_DELIM = '\n' + ' ' * 4
INACTIVITY_TIMEOUT = 10.0
MSG_QUIT = "QUIT"
MSG_TIMEOUT = "TIMEOUT"
SLEEP_INTERVAL = 0.01


def async_map(coroutine, iterator):
    """Map iterator iterator onto a coroutine.

    * Yields results in order as and when they are ready.
    * Slow workers can block.

    Args:
        coroutine (asyncio.coroutine):
            I.E. an async function.
        iterator (iter):
            Should yield tuples to be passed into the coroutine.

    Yields:
        list - List of results.

    Example:
        >>> async def square(number): return number ** 2
        >>> generator = async_map(square, ((i,) for i in range(5)))
        >>> list(generator)
        [0, 1, 4, 9, 16]

    """
    loop = asyncio.get_event_loop()

    awaiting = []
    for ind, args in enumerate(iterator):
        task = loop.create_task(coroutine(*args))
        task.ind = ind
        awaiting.append(task)

    index = 0
    completed_tasks = {}
    while awaiting:
        completed, awaiting = loop.run_until_complete(
            asyncio.wait(awaiting, return_when=asyncio.FIRST_COMPLETED))
        completed_tasks.update({t.ind: t.result() for t in completed})

        changed = True
        while changed and completed_tasks:
            if index in completed_tasks:
                yield completed_tasks.pop(index)
                changed = True
                index += 1


def async_unordered_map(coroutine, iterator):
    """Map iterator iterator onto a coroutine.

    Args:
        coroutine (asyncio.coroutine):
            I.E. an async function.
        iterator (iter):
            Should yield tuples to be passed into the coroutine.

    Yields:
        tuple - (args, result)

    Example:
        >>> async def square(number): return number ** 2
        >>> generator = async_unordered_map(square, ((i,) for i in range(5)))
        >>> sorted(list(generator))
        [((0,), 0), ((1,), 1), ((2,), 4), ((3,), 9), ((4,), 16)]

    """
    loop = asyncio.get_event_loop()

    awaiting = []
    for args in iterator:
        task = loop.create_task(coroutine(*args))
        task.args = args
        awaiting.append(task)

    while awaiting:
        completed, awaiting = loop.run_until_complete(
            asyncio.wait(awaiting, return_when=asyncio.FIRST_COMPLETED))
        for task in completed:
            yield (task.args, task.result())


def scan_many(items, methods=None, timeout=None, ordered=False):
    """Call "identify" method of suites on many host:port.

    Args:
        items (list): list of 'host' string or ('host', port) tuple to scan.
        methods (list): list of 'method' string to be executed when scanning.
        timeout (float): connection timeout, default is CONNECT_TIMEOUT.
        ordered (bool): whether to scan items in order or not (default).

    Return:
        list: [(host, port, identify_result), ...]

    """
    args = ((reg, host, port, timeout, methods) for reg, host, port in items)

    if ordered:
        yield from async_map(scan_one, args)
    else:
        yield from (
            result for _, result in async_unordered_map(scan_one, args))


async def scan_one(reg, host, port, timeout=None, methods=None):
    if not methods:
        methods = ['identify']

    if is_remote_host(host):
        try:
            host = get_host_ip_by_name(host)  # IP reduces DNS traffic
        except socket.error as exc:
            if cylc.flags.debug:
                raise
            sys.stderr.write("ERROR: %s: %s\n" % (exc, host))
            return (reg, host, port, None)

    # NOTE: Connect to the suite by host:port, this was the
    #       SuiteRuntimeClient will not attempt to check the contact file
    #       which would be unnecessary as we have already done so.
    # NOTE: This part of the scan *is* IO blocking.
    client = SuiteRuntimeClient(reg, host=host, port=port, timeout=timeout)

    result = {}
    for method in methods:
        # work our way up the chain of identity methods, extract as much
        # information as we can before the suite rejects us
        try:
            msg = await client.async_request(method)
        except ClientTimeout as exc:
            return (reg, host, port, MSG_TIMEOUT)
        except ClientError as exc:
            return (reg, host, port, result or None)
        else:
            result.update(msg)
    return (reg, host, port, result)


def re_compile_filters(patterns_owner=None, patterns_name=None):
    """Compile regexp for suite owner and suite name scan filters.

    Arguments:
        patterns_owner (list): List of suite owner patterns
        patterns_name (list): List of suite name patterns

    Returns (tuple):
        A 2-element tuple in the form (cre_owner, cre_name). Either or both
        element can be None to allow for the default scan behaviour.
    """
    cres = {'owner': None, 'name': None}
    for label, items in [('owner', patterns_owner), ('name', patterns_name)]:
        if items:
            cres[label] = r'\A(?:' + r')|(?:'.join(items) + r')\Z'
            try:
                cres[label] = re.compile(cres[label])
            except re.error:
                raise ValueError(r'%s=%s: bad regexp' % (label, items))
    return (cres['owner'], cres['name'])


def get_scan_items_from_fs(owner_pattern=None, reg_pattern=None):
    """Scrape list of suites from the filesystem.

    Walk users' "~/cylc-run/" to get (host, port) from ".service/contact" for
    active suites.

    Yields:
        tuple - (reg, host, port)

    """
    srv_files_mgr = SuiteSrvFilesManager()
    if owner_pattern is None:
        # Run directory of current user only
        run_dirs = [(glbl_cfg().get_host_item('run directory'), None)]
    else:
        # Run directory of all users matching "owner_pattern".
        # But skip those with /nologin or /false shells
        run_dirs = []
        skips = ('/false', '/nologin')
        for pwent in getpwall():
            if any(pwent.pw_shell.endswith(s) for s in (skips)):
                continue
            if owner_pattern.match(pwent.pw_name):
                run_dirs.append((
                    glbl_cfg().get_host_item(
                        'run directory',
                        owner=pwent.pw_name,
                        owner_home=pwent.pw_dir),
                    pwent.pw_name))
    if cylc.flags.debug:
        sys.stderr.write('Listing suites:%s%s\n' % (
            DEBUG_DELIM, DEBUG_DELIM.join(item[1] for item in run_dirs if
                                          item[1] is not None)))
    for run_d, owner in run_dirs:
        for dirpath, dnames, _ in os.walk(run_d, followlinks=True):
            # Always descend for top directory, but
            # don't descend further if it has a .service/ or log/ dir
            if dirpath != run_d and (
                    srv_files_mgr.DIR_BASE_SRV in dnames or 'log' in dnames):
                dnames[:] = []

            # Filter suites by name
            reg = os.path.relpath(dirpath, run_d)
            if reg_pattern and not reg_pattern.match(reg):
                continue

            # Choose only suites with .service and matching filter
            try:
                contact_data = srv_files_mgr.load_contact_file(reg, owner)
            except (SuiteServiceFileError, IOError, TypeError, ValueError):
                continue
            else:
                yield (
                    reg,
                    contact_data[srv_files_mgr.KEY_HOST],
                    contact_data[srv_files_mgr.KEY_PORT]
                )
