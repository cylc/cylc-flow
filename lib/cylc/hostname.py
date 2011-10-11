#!/usr/bin/env python

import sys, socket

# If getfqdn() returns a bad Fully Qualified Domain Name due to problems
# with the local host networking settings (or DNS?) try gethostname().
try:
    hostname = socket.getfqdn()
    socket.gethostbyname(hostname)  # test hostname valid in DNS
#except socket.gaierror:  # (any exception here will do)
except:
    print >> sys.stderr, "WARNING from cylc.hostname:"
    print >> sys.stderr, "  Something appears to be wrong with your local network settings."
    print >> sys.stderr, "  Python 'socket.getfqdn()' should be equivalent to 'hostname -f'"
    print >> sys.stderr, "  but it returned an invalid hostname; trying 'gethostname()' ..."
    try:
        hostname = socket.gethostname()
        socket.gethostbyname(hostname)   # test hostname valid in DNS
        print >> sys.stderr, "  ... got", hostname
    #except socket.gaierror:  # (any exception here will do)
    except:
        print >> sys.stderr, "ERROR: Unable to determine hostname. Check network settings."
        sys.exit(1)
