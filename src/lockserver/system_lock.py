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

groupname = ':cylc-lockserver'
name = 'broker'

from lockserver import get_lockserver

class system_lock:
    def __init__( self, pns_host, username, sysname, system_dir, cylc_mode ):

        self.pns_host = pns_host
        self.system_dir = system_dir
        self.cylc_mode = cylc_mode

        self.lockgroup = username + '.' + sysname


    def request_system_access( self, exclusive=True ):
        # Cylc system name is user-specific (i.e. different users can
        # register systems with the same name), but the cylc groupname
        # (USERNAME^SYSTEMNAME) is unique (because two users cannot have
        # the same username).        

        # System config files should specify whether or not a system is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire system at
        # once? 
        
        # GET A NEW CONNECTION WITH EACH REQUEST
        # TO DO: OR GET A SINGLE CONNECTION IN INIT

        server = get_lockserver( self.pns_host )
        (result, reason) = server.get_system_access( self.system_dir, self.lockgroup, self.cylc_mode, exclusive )
        if not result:
            print >> sys.stderr, 'ERROR, failed to get system access:'
            print >> sys.stderr, reason
            return False
        else:
           return True

    def release_system_access( self):
        server = get_lockserver( self.pns_host )
        result = server.release_system_access( self.system_dir, self.lockgroup )
        if not result:
            print >> sys.stderr, 'WARNING, failed to release system access'
            return False
        else:
           return True
