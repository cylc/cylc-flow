#!/usr/bin/python

class sequential:
    # not "ready to spawn" unless 'finished'.
    def ready_to_spawn( self ):
        if self.state.has_spawnd():
            return False
        if self.state.is_finished():
            return True
        else:
            return False
