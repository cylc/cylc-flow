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
"""Host name utilities

ATTRIBUTION:
https://web.archive.org/web/20140606052543/http://www.linux-support.com/cms/get-local-ip-address-with-python/

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

from contextlib import suppress
import os
import pwd
import socket
import sys
from time import time

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg


IS_MAC_OS = 'darwin' in sys.platform.lower()


class HostUtil:
    """host and user ID utility."""

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
        self._host = None  # preferred name of localhost
        self._host_exs = {}  # host: socket.gethostbyname_ex(host), ...
        self._remote_hosts = {}  # host: is_remote, ...
        self.user_pwent = None
        self.remote_users = {}

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
        with suppress(IOError):  # noqa: SIM117 (use of as convolutes this)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((target, 8000))
                ipaddr = sock.getsockname()[0]
        return ipaddr

    @staticmethod
    def get_host_ip_by_name(target):
        """Return internal IP address of target."""
        return socket.gethostbyname(target)

    def _get_host_info(self, target=None):
        """Return the extended info of the current host."""
        if target not in self._host_exs:
            if target is None:
                target = socket.getfqdn()
            if (
                IS_MAC_OS
                and target in {
                    '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.'
                    '0.0.0.0.0.0.ip6.arpa',
                    '1.0.0.127.in-addr.arpa'
                }
            ):
                # Python's socket bindings don't play nicely with mac os
                # so by default we get the above ip6.arpa address from
                # socket.getfqdn, note this does *not* match `hostname -f`.
                # https://github.com/cylc/cylc-flow/issues/2689
                # https://github.com/cylc/cylc-flow/issues/3595
                target = socket.gethostname()
            try:
                self._host_exs[target] = socket.gethostbyname_ex(target)
            except IOError as exc:
                if exc.filename is None:
                    exc.filename = target
                raise
        return self._host_exs[target]

    @staticmethod
    def _get_identification_cfg(key):
        """Return the [workflow host self-identification]key global conf."""
        return glbl_cfg().get(['scheduler', 'host self-identification', key])

    def get_host(self):
        """Return the preferred identifier for the workflow (or current) host.

        As specified by the "[scheduler][host self-identification]" settings in
        the site/user global.cylc files. This is mainly used for workflow host
        identification by tasks.

        """
        if self._host is None:
            hardwired = self._get_identification_cfg('host')
            method = self._get_identification_cfg('method')
            if method == 'address':
                self._host = self.get_local_ip_address(
                    self._get_identification_cfg('target'))
            elif method == 'hardwired' and hardwired:
                self._host = hardwired
            else:  # if method == 'name':
                self._host = self._get_host_info()[0]
        return self._host

    def get_fqdn_by_host(self, target):
        """Return the fully qualified domain name of the target host."""
        if not self.is_remote_host(target):
            return self.get_host()
        return self._get_host_info(target)[0]

    def get_user(self):
        """Return name of current user."""
        return self._get_user_pwent().pw_name

    def get_user_home(self):
        """Return home directory of current user."""
        return self._get_user_pwent().pw_dir

    def _get_user_pwent(self):
        """Ensure self.user_pwent is set to current user's password entry."""
        if self.user_pwent is None:
            my_user_name = os.environ.get('USER')
            if my_user_name:
                self.user_pwent = pwd.getpwnam(my_user_name)
            else:
                self.user_pwent = pwd.getpwuid(os.getuid())
            self.remote_users.update(((self.user_pwent.pw_name, False),))
        return self.user_pwent

    def is_remote_host(self, name):
        """Return True if name has different IP address than the current host.

        Return False if name is None.
        Return True if host is unknown.

        """
        if name not in self._remote_hosts:
            if not name or name.startswith("localhost"):
                # e.g. localhost4.localdomain4
                self._remote_hosts[name] = False
            else:
                try:
                    host_info = self._get_host_info(name)
                except IOError:
                    self._remote_hosts[name] = True
                else:
                    self._remote_hosts[name] = (
                        host_info != self._get_host_info())
        return self._remote_hosts[name]

    def is_remote_user(self, name):
        """Return True if name is not a name of the current user.

        Return False if name is None.
        Return True if name is not in the password database.
        """
        if not name:
            return False
        if name not in self.remote_users:
            try:
                self.remote_users[name] = (
                    pwd.getpwnam(name) != self._get_user_pwent())
            except KeyError:
                self.remote_users[name] = True
        return self.remote_users[name]

    def _is_remote_platform(self, platform):
        """Return True if any job host in platform have different IP address
        to the current host.

        Return False if name is None.
        Return True if host is unknown.

        Todo:
            Should this fail miserably if some hosts are remote and some are
            not?
        """
        if not platform:
            return False
        return any(
            is_remote_host(host)
            for host in platform['hosts']
        )


def get_host_ip_by_name(target):
    """Shorthand for HostUtil.get_inst().get_host_ip_by_name(target)."""
    return HostUtil.get_inst().get_host_ip_by_name(target)


def get_local_ip_address(target):
    """Shorthand for HostUtil.get_inst().get_local_ip_address(target)."""
    return HostUtil.get_inst().get_local_ip_address(target)


def get_host():
    """Shorthand for HostUtil.get_inst().get_host()."""
    return HostUtil.get_inst().get_host()


def get_fqdn_by_host(target):
    """Shorthand for HostUtil.get_inst().get_fqdn_by_host(target)."""
    return HostUtil.get_inst().get_fqdn_by_host(target)


def get_user():
    """Shorthand for HostUtil.get_inst().get_user()."""
    return HostUtil.get_inst().get_user()


def get_user_home():
    """Shorthand for HostUtil.get_inst().get_user_home()."""
    return HostUtil.get_inst().get_user_home()


def is_remote_platform(platform):
    """Shorthand for HostUtil.get_inst()._is_remote_platform(host, owner)."""
    return HostUtil.get_inst()._is_remote_platform(platform)


def is_remote_host(name):
    """Shorthand for HostUtil.get_inst().is_remote_host(name)."""
    return HostUtil.get_inst().is_remote_host(name)


def is_remote_user(name):
    """Return True if name is not a name of the current user."""
    return HostUtil.get_inst().is_remote_user(name)
