#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
"""Host name utilities

ATTRIBUTION:
http://www.linux-support.com/cms/get-local-ip-address-with-python/

Fetching the outgoing IP address of a computer might be a difficult
task. Computers can contain a large set of network devices, each
connected to different and independent sub-networks. Additionally there
might be available a number of devices, to be utilized in the manner of
network devices to exchange data with external systems.

However, if properly configured, your operating system knows what device
has to be utilized. Querying results depend on target addresses and
routing information. In our solution we are utilizing the features of
the local operating system to determine the correct network device. It is
the same step we will get the associated network address.

To reach this goal we will utilize the UDP protocol. Unlike TCP/IP, UDP
is a stateless networking protocol to transfer single data packages. You
do not have to open a point-to-point connection to a service running at
the target host. We have to provide the target address to enable the
operating system to find the correct device. Due to the nature of UDP
you are not required to choose a valid target address. You just have to
make sure your are choosing an arbitrary address from the correct
subnet.

The following function is temporarily opening a UDP server socket. It is
returning the IP address associated with this socket.

"""

import sys
import socket
from time import time


class SuiteHostUtil(object):
    """(Suite) host utility."""

    EXPIRE = 3600.0  # singleton expires in 1 hour by default
    _instance = None

    @classmethod
    def get_inst(cls, new=False, expire=None):
        """Return the singleton instance of this class.

        "new": if True, create a new singleton instance.
        "expire":
            the expire duration in seconds. If None or not specified, the
            singleton expires after 3600.0 seconds (1 hour). Once expired, the
            next call to this method will create a new singleton.

        """
        if expire is None:
            expire = cls.EXPIRE
        if cls._instance is None or new or time() > cls._instance.expire_time:
            cls._instance = cls(expire)
        return cls._instance

    def __init__(self, expire):
        self.expire_time = time() + expire
        self._host_name = None
        self._host_ip_address = None
        self._host_name_pref = None
        self._remote_hosts = {}  # host: is_remote, ...

    @staticmethod
    def get_local_ip_address(target):
        """Return IP address of target.

        This finds the external address of the particular network adapter
        responsible for connecting to the target?

        Note that although no connection is made to the target, the target
        must be reachable on the network (or just recorded in the DNS?) or
        the function will hang and time out after a few seconds.

        """

        ipaddr = ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((target, 8000))
            ipaddr = sock.getsockname()[0]
            sock.close()
        except IOError:
            pass
        return ipaddr

    def get_hostname(self):
        """Return the fully qualified domain name for current host."""
        if self._host_name is None:
            self._host_name = socket.getfqdn()
        return self._host_name

    def _get_host_ip_address(self):
        """Return the external IP address for the current host."""
        if self._host_ip_address is None:
            self._host_ip_address = self.get_local_ip_address(
                self._get_identification_cfg('target'))
        return self._host_ip_address

    @staticmethod
    def _get_identification_cfg(key):
        """Return the [suite host self-identification]key global conf."""
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        return GLOBAL_CFG.get(['suite host self-identification', key])

    def get_suite_host(self):
        """Return the preferred identifier for the suite (or current) host.

        As specified by the "suite host self-identification" settings in the
        site/user global.rc files. This is mainly used for suite host
        identification by task jobs.

        """
        if self._host_name_pref is None:
            hardwired = self._get_identification_cfg('host')
            method = self._get_identification_cfg('method')
            if method == 'address':
                self._host_name_pref = self._get_host_ip_address()
            elif method == 'hardwired' and hardwired:
                self._host_name_pref = hardwired
            else:  # if method == 'name':
                self._host_name_pref = self.get_hostname()
        return self._host_name_pref

    def is_remote_host(self, name):
        """Return True if name has different IP address than the current host.

        Return False if name is None.
        Raise IOError if host is unknown.

        """
        if name not in self._remote_hosts:
            if not name or name.split(".")[0].startswith("localhost"):
                # e.g. localhost.localdomain
                self._remote_hosts[name] = False
            else:
                try:
                    ipa = socket.gethostbyname(name)
                except IOError as exc:
                    if exc.filename is None:
                        exc.filename = str(name)
                    raise
                host_ip_address = self._get_host_ip_address()
                # local IP address of the suite host (e.g. 127.0.0.1)
                local_ip_address = socket.gethostbyname(self.get_hostname())
                self._remote_hosts[name] = (
                    ipa not in [host_ip_address, local_ip_address])
        return self._remote_hosts[name]


def get_hostname():
    """Shorthand for SuiteHostUtil.get_inst().get_hostname()."""
    return SuiteHostUtil.get_inst().get_hostname()


def get_local_ip_address(target):
    """Shorthand for SuiteHostUtil.get_inst().get_local_ip_address(target)."""
    return SuiteHostUtil.get_inst().get_local_ip_address(target)


def get_suite_host():
    """Shorthand for SuiteHostUtil.get_inst().get_suite_host()."""
    return SuiteHostUtil.get_inst().get_suite_host()


def is_remote_host(name):
    """Shorthand for SuiteHostUtil.get_inst().is_remote_host(name)."""
    return SuiteHostUtil.get_inst().is_remote_host(name)


if __name__ == "__main__":
    sys.stdout.write("%s\n" % get_local_ip_address(sys.argv[1]))
