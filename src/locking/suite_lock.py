#!/usr/bin/env python

import Pyro.core
import os,sys,socket
import os

from lockserver import lockserver

class suite_lock(object):
    def __init__( self, suite, suite_dir, host, port, cylc_mode ):
        self.host = host
        self.port = port
        self.suite_dir = suite_dir
        self.cylc_mode = cylc_mode
        self.suite = suite

    def request_suite_access( self, exclusive=True ):
        # suite config files should specify whether or not a suite is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire suite at
        # once? 
        
        # GET A NEW CONNECTION WITH EACH REQUEST
        # TO DO: OR GET A SINGLE CONNECTION IN INIT

        server = lockserver( self.host, self.port ).get()
        (result, reason) = server.get_suite_access( self.suite_dir, self.suite, self.cylc_mode, exclusive )
        if not result:
            print >> sys.stderr, 'ERROR, failed to get suite access:'
            print >> sys.stderr, reason
            return False
        else:
           return True

    def release_suite_access( self):
        server = lockserver( self.host, self.port ).get()
        result = server.release_suite_access( self.suite_dir, self.suite )
        if not result:
            return False
        else:
           return True
