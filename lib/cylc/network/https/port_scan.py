#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

from multiprocessing import cpu_count, Pool
import sys
from time import sleep
import traceback
from uuid import uuid4

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.network import NO_PASSPHRASE, ConnectionDeniedError
from cylc.network.https.suite_state_client import SuiteStillInitialisingError
from cylc.network.https.suite_identifier_client import (
    SuiteIdClientAnon, SuiteIdClient)
from cylc.owner import USER
from cylc.registration import RegistrationDB
from cylc.suite_host import get_hostname, is_remote_host


def scan(host=None, db=None, timeout=None):
    """Scan ports, return a list of suites found: [(port, suite.identify())].

    Note that we could easily scan for a given suite+owner and return its
    port instead of reading port files, but this may not always be fast enough.
    """
    if host is None:
        host = get_hostname()
    base_port = GLOBAL_CFG.get(
        ['communication', 'base port'])
    last_port = base_port + GLOBAL_CFG.get(
        ['communication', 'maximum number of ports'])
    if timeout:
        timeout = float(timeout)
    else:
        timeout = None

    reg_db = RegistrationDB(db)
    results = []
    my_uuid = uuid4()
    for port in range(base_port, last_port):
        client = SuiteIdClientAnon(None, host=host, port=port, my_uuid=my_uuid)
        try:
            result = (port, client.identify())
        except ConnectionDeniedError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            continue
        except Exception as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            raise
        else:
            owner = result[1].get('owner')
            name = result[1].get('name')
            states = result[1].get('states', None)
            if cylc.flags.debug:
                print '   suite:', name, owner
            if states is None:
                # This suite keeps its state info private.
                # Try again with the passphrase if I have it.
                pphrase = reg_db.load_passphrase(name, owner, host)
                if pphrase:
                    client = SuiteIdClient(name, owner=owner, host=host,
                                           port=port, my_uuid=my_uuid,
                                           timeout=timeout)
                    try:
                        result = (port, client.identify())
                    except Exception:
                        # Nope (private suite, wrong passphrase).
                        if cylc.flags.debug:
                            print '    (wrong passphrase)'
                    else:
                        reg_db.cache_passphrase(
                            name, owner, host, pphrase)
                        if cylc.flags.debug:
                            print '    (got states with passphrase)'
        results.append(result)
    return results


def scan_all(hosts=None, reg_db_path=None, timeout=None):
    """Scan all hosts."""
    if not hosts:
        hosts = GLOBAL_CFG.get(["suite host scanning", "hosts"])
    # Ensure that it does "localhost" only once
    hosts = set(hosts)
    for host in list(hosts):
        if not is_remote_host(host):
            hosts.remove(host)
            hosts.add("localhost")
    proc_pool_size = GLOBAL_CFG.get(["process pool size"])
    if proc_pool_size is None:
        proc_pool_size = cpu_count()
    if proc_pool_size > len(hosts):
        proc_pool_size = len(hosts)
    proc_pool = Pool(proc_pool_size)
    async_results = {}
    for host in hosts:
        async_results[host] = proc_pool.apply_async(
            scan, [host, reg_db_path, timeout])
    proc_pool.close()
    scan_results = []
    scan_results_hosts = []
    while async_results:
        sleep(0.05)
        for host, async_result in async_results.items():
            if async_result.ready():
                async_results.pop(host)
                try:
                    res = async_result.get()
                except Exception:
                    if cylc.flags.debug:
                        traceback.print_exc()
                else:
                    scan_results.extend(res)
                    scan_results_hosts.extend([host] * len(res))
    proc_pool.join()
    return zip(scan_results_hosts, scan_results)
