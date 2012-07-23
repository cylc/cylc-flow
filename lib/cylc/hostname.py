#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

# If getfqdn() returns a bad Fully Qualified Domain Name due to problems
# with the local host networking settings (or DNS?) try gethostname().
try:
    hostname = socket.getfqdn()
    host_ip_address = socket.gethostbyname(hostname) # test hostname valid in DNS
    shorthostname = re.sub( '\..*', '', hostname )
#except socket.gaierror:  # (any exception here will do)
except:
    print >> sys.stderr, "WARNING from cylc.hostname:"
    print >> sys.stderr, "  Something appears to be wrong with your local network settings."
    print >> sys.stderr, "  Python 'socket.getfqdn()' should be equivalent to 'hostname -f'"
    print >> sys.stderr, "  but it returned an invalid hostname; trying 'gethostname()' ..."
    try:
        hostname = socket.gethostname()
        host_ip_address = socket.gethostbyname(hostname) # test hostname valid in DNS
        print >> sys.stderr, "  ... got", hostname
    #except socket.gaierror:  # (any exception here will do)
    except:
        print >> sys.stderr, "ERROR: Unable to determine hostname. Check network settings."
        sys.exit(1)

def is_remote_host(name):
    """Return True if name has different IP address than the current host.
    Return False if name is None.  Abort if host is unknown.
    """
    if not name:
        return False
    try:
        ipa = socket.gethostbyname(name) 
    except Exception, e:
        print >> sys.stderr, str(e)
        sys.exit( 'ERROR, host not found: ' + name )
    return name and ipa != host_ip_address

