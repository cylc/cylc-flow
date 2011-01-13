#!/usr/bin/env python


# always claim to have spawned already

class oneoff(object):

    is_oneoff = True  # used in manager

    def ready_to_spawn( self ):
        self.state.set_spawned()
        return False

    def has_spawned( self ):
        return True
