#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re, sys, socket

hostname = None
suite_host = None
host_ip_address = None

def get_local_ip_address( target ):
    """
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
the local operating system to determine the correct network device. I
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

    # This finds the external address of the particular network adapter
    # responsible for connecting to the target?

    # Note that although no connection is made to the target, the target
    # must be reachable on the network (or just recorded in the DNS?) or
    # the function will hang and time out after a few seconds.

    ipaddr = ''
    try:
        s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        s.connect( (target, 8000) )
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        pass
    return ipaddr

def get_hostname():
    global hostname
    if hostname is None:
        hostname = socket.getfqdn()
    return hostname

def get_host_ip_address():
    from cylc.cfgspec.globalcfg import GLOBAL_CFG
    global host_ip_address
    if host_ip_address is None:
        target = GLOBAL_CFG.get( ['suite host self-identification','target'] )
        # external IP address of the suite host:
        host_ip_address = get_local_ip_address( target )
    return host_ip_address

def get_suite_host():
    from cylc.cfgspec.globalcfg import GLOBAL_CFG
    global suite_host
    if suite_host is None:
        hardwired = GLOBAL_CFG.get( ['suite host self-identification','host'] )
        method = GLOBAL_CFG.get( ['suite host self-identification','method'] )
        # the following is for suite host self-identfication in task job scripts:
        if method == 'name':
            suite_host = hostname
        elif method == 'address':
            suite_host = get_host_ip_address()
        elif method == 'hardwired':
            if not hardwired:
                sys.exit( 'ERROR, no hardwired hostname is configured' )
            suite_host = hardwired
        else:
            sys.exit( 'ERROR, unknown host method: ' + method )
    return suite_host

def is_remote_host(name):
    """Return True if name has different IP address than the current host.
    Return False if name is None.  Abort if host is unknown.
    """
    if name is None or name.startswith("localhost"):
        # e.g. localhost.localdomain
        return False
    try:
        ipa = socket.gethostbyname(name)
    except Exception, e:
        print >> sys.stderr, str(e)
        raise Exception( 'ERROR, host not found: ' + name )
    host_ip_address = get_host_ip_address()
    # local IP address of the suite host (may be 127.0.0.1, for e.g.)
    local_ip_address = socket.gethostbyname(get_hostname())
    return name and ipa != host_ip_address and ipa != local_ip_address

if __name__ == "__main__":

    target = sys.argv[1]
    print get_local_ip_address( target )
