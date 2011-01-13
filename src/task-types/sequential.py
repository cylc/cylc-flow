#!/usr/bin/env python


class sequential(object):
    # not "ready to spawn" unless 'finished'.
    def ready_to_spawn( self ):
        if self.state.is_finished() and not self.state.has_spawned():
            return True
        else:
            return False
