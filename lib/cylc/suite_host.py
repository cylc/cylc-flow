#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import sys, socket
import logging
from global_config import gcfg
import datetime

"""SUITE HOST IDENTIFICATION IN CYLC: to avoid potential delays
due to host lookup, the suite host self-identifies to local tasks as
'localhost', requiring no host lookup. If there are any remote tasks,
suite host lookup is done once in the job submission thread when the
first remote task is about to be submitted (and then remembered here for
other remote tasks).
TASK HOST IDENTIFICATION IN CYLC: if a task specifies 'localhost' or no
host at all under [remote] it will be treated as a local task; otherwise
it will be submitted by ssh as a remote task even if it is actually a
local task.  This allows us to avoid doing any host lookup for suites
containing only local tasks, and also to test remote hosting
functionality without an actual remote host, by specifying the
suite host's external host name or IP address as a task host, rather
than 'localhost'.""" 

log = logging.getLogger( "main" )
 
host = None

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
    # the function will hang and time out after a few (e.g. 20!) seconds.

    # TODO - is it conceivable that different remote task hosts at the
    # same site might see the suite host differently? If so we would
    # need to be able to override the target in suite definitions.)

    ipaddr = ''
    try:
        s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        s.connect( (target, 8000) )
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        pass
    return ipaddr

def get_host():
    """Return the current host by hostname, external IP address, or
    hardwired (determined by site/user config files."""

    global host
    # lazy evaluation, to avoid dns additional lookup delays
    if host:
        # already computed
        return host

    method = gcfg.cfg['suite host self-identification']['method']
    target = gcfg.cfg['suite host self-identification']['target']
    hardwired = gcfg.cfg['suite host self-identification']['host']

    tstart = datetime.datetime.now()

    # for suite host self-identfication in task job scripts:
    if method == 'name':
        host = socket.getfqdn()
        # internal_ip_address = socket.gethostbyname(host)  # (not needed)
    elif method == 'address':
        # external IP address of the suite host (as seen by others)
        host = get_local_ip_address( target )
    elif method == 'hardwired':
        host = hardwired
    else:
        # can't happen due to config parse checking
        sys.exit( 'ERROR, unknown host method: ' + method )

    tdelta = datetime.datetime.now() - tstart
    seconds = tdelta.seconds + float(tdelta.microseconds)/10**6
    if method == 'hardwired':
        log.debug( "suite host hardwired to " + host )
    else:
        log.debug( "suite host " + host + " (lookup took " + str( seconds ) + " seconds)" )

    return host
 
if __name__ == "__main__":

    target = sys.argv[1]
    print get_local_ip_address( target )

