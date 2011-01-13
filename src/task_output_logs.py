#!/usr/bin/env python

import re

from interp_env import interp_local_str, interp_other_str

class logfiles( object ):
    # we need task output logs file to be mutable (i.e. not just strings) so
    # that changes to log paths in the job submit class are reflected in
    # the task class.
    def __init__( self, path = None ):
        self.paths = []
        if path:
            self.paths.append( path )

    def add_path( self, path ):
        self.paths.append( path )

    def add_path_prepend( self, path ):
        self.paths = [ path ] + self.paths

    def replace_path( self, pattern, path, prepend=True ):
        # replace a path that matches a pattern with another path
        # (used to replace output logs when a failed task is reset)
        for item in self.paths:
            if re.match( pattern, item ):
                #print 'REPLACING', item, 'WITH', path
                self.paths.remove( item )
                break
        # add the new path even if a match to replace wasn't found
        if prepend:
            self.add_path_prepend( path )
        else:
            self.add_path( path )

    def get_paths( self ):
        return self.paths

    def empty( self ):
        self.paths = []

    def interpolate( self, env = None ):
        new_paths = []
        for log in self.paths:
            if env:
                log = interp_other_str( log, env )
            else:
                log = interp_local_str( log )
            new_paths.append( log )

        self.paths = new_paths
