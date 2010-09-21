#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.core
import os,sys,socket
import os

from lockserver import lockserver

class suite_lock:
    def __init__( self, pns_host, username, suitename, suite_dir, cylc_mode ):

        self.pns_host = pns_host
        self.suite_dir = suite_dir
        self.cylc_mode = cylc_mode
        self.lockgroup = username + '.' + suitename

    def request_suite_access( self, exclusive=True ):
        # Cylc suite name is user-specific (i.e. different users can
        # register suites with the same name), but the cylc groupname
        # (USERNAME^SUITENAME) is unique (because two users cannot have
        # the same username).        

        # suite config files should specify whether or not a suite is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire suite at
        # once? 
        
        # GET A NEW CONNECTION WITH EACH REQUEST
        # TO DO: OR GET A SINGLE CONNECTION IN INIT

        server = lockserver( self.pns_host ).get()
        (result, reason) = server.get_suite_access( self.suite_dir, self.lockgroup, self.cylc_mode, exclusive )
        if not result:
            print >> sys.stderr, 'ERROR, failed to get suite access:'
            print >> sys.stderr, reason
            return False
        else:
           return True

    def release_suite_access( self):
        server = lockserver( self.pns_host ).get()
        result = server.release_suite_access( self.suite_dir, self.lockgroup )
        if not result:
            print >> sys.stderr, 'WARNING, failed to release suite access'
            return False
        else:
           return True
