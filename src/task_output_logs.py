#!/usr/bin/env python

from interp_env import interp_self, interp_other, interp_local, interp_local_str, replace_delayed, interp_other_str, replace_delayed_str

class logfiles:
    # we need task output logs file to be mutable (i.e. not just strings) so
    # that changes to log paths in the job submit class are reflected in
    # the task class.
    def __init__( self, path = None ):
        self.paths = []
        if path:
            self.paths.append( path )

    def add_path( self, path ):
        self.paths.append( path )

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

