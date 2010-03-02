#!/usr/bin/python

# always claim to have spawned already

class oneoff:
    def ready_to_spawn( self ):
        self.state.set_spawned()

    def has_spawned( self ):
        return True
