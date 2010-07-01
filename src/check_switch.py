#!/usr/bin/env python

# a trivial function for checking the result of remote switch calls in
# all cylc commands; so that they exit with error status if the command
# fails.  This can't be put in the remote switch file as it imports the
# system tasks.

import sys

def check( result ):
    print result
    if result != "OK":
        sys.exit(1)
