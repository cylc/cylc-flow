#!/usr/bin/pyro

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
"""Pyro port scan utilities."""

from multiprocessing import cpu_count, Pool
import sys
from time import sleep
import traceback

import Pyro.errors
import Pyro.core

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.network import PYRO_SUITEID_OBJ_NAME, NO_PASSPHRASE
from cylc.network.connection_validator import ConnValidator, SCAN_HASH
from cylc.network.suite_state import SuiteStillInitialisingError
from cylc.owner import USER
from cylc.registration import RegistrationDB
from cylc.suite_host import get_hostname, is_remote_host


def get_proxy(host, port, pyro_timeout):
    """Return Pyro URL of proxy."""
    proxy = Pyro.core.getProxyForURI(
        'PYROLOC://%s:%s/%s' % (host, port, PYRO_SUITEID_OBJ_NAME))
    proxy._setTimeout(pyro_timeout)
    return proxy


def scan(host=None, db=None, pyro_timeout=None):
    """Scan ports, return a list of suites found: [(port, suite.identify())].

    Note that we could easily scan for a given suite+owner and return its
    port instead of reading port files, but this may not always be fast enough.
    """
    if host is None:
        host = get_hostname()
    base_port = GLOBAL_CFG.get(['pyro', 'base port'])
    last_port = base_port + GLOBAL_CFG.get(['pyro', 'maximum number of ports'])
    if pyro_timeout:
        pyro_timeout = float(pyro_timeout)
    else:
        pyro_timeout = None

    reg_db = RegistrationDB(db)
    results = []
    for port in range(base_port, last_port):
        try:
            proxy = get_proxy(host, port, pyro_timeout)
            conn_val = ConnValidator()
            conn_val.set_default_hash(SCAN_HASH)
            proxy._setNewConnectionValidator(conn_val)
            proxy._setIdentification((USER, NO_PASSPHRASE))
            result = (port, proxy.identify())
        except Pyro.errors.ConnectionDeniedError as exc:
            if cylc.flags.debug:
                print '%s:%s (connection denied)' % (host, port)
            # Back-compat <= 6.4.1
            msg = '  Old daemon at %s:%s?' % (host, port)
            for pphrase in reg_db.load_all_passphrases():
                try:
                    proxy = get_proxy(host, port, pyro_timeout)
                    proxy._setIdentification(pphrase)
                    info = proxy.id()
                    result = (port, {'name': info[0], 'owner': info[1]})
                except Pyro.errors.ConnectionDeniedError:
                    connected = False
                else:
                    connected = True
                    break
            if not connected:
                if cylc.flags.verbose:
                    print >> sys.stderr, msg, "- connection denied (%s)" % exc
                continue
            else:
                if cylc.flags.verbose:
                    print >> sys.stderr, msg, "- connected with passphrase"
        except Pyro.errors.TimeoutError as exc:
            # E.g. Ctrl-Z suspended suite - holds up port scanning!
            if cylc.flags.debug:
                print '%s:%s (connection timed out)' % (host, port)
            print >> sys.stderr, (
                'suite? owner?@%s:%s - connection timed out (%s)' % (
                    host, port, exc))
            continue
        except (Pyro.errors.ProtocolError, Pyro.errors.NamingError) as exc:
            # No suite at this port.
            if cylc.flags.debug:
                print str(exc)
                print '%s:%s (no suite)' % (host, port)
            continue
        except SuiteStillInitialisingError:
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
                    try:
                        proxy = get_proxy(host, port, pyro_timeout)
                        conn_val = ConnValidator()
                        conn_val.set_default_hash(SCAN_HASH)
                        proxy._setNewConnectionValidator(conn_val)
                        proxy._setIdentification((USER, pphrase))
                        result = (port, proxy.identify())
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


def scan_all(hosts=None, reg_db_path=None, pyro_timeout=None):
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
            scan, [host, reg_db_path, pyro_timeout])
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
