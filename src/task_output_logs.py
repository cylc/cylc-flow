#!/usr/bin/env python

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
