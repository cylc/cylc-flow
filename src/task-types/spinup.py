#!/usr/bin/env python

class spinup(object):
    """
A task with a final cycle time. If the final cycle time has been
reached, report that I've spawned already so that a successor will
not be spawned.
    """

    def has_spawned( self ):
        if int( self.c_time ) >= int( self.final_cycle_time ):
            self.state.set_spawned()
            return True
        else: 
            return self.state.has_spawned()

