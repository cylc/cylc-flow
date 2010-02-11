#!/usr/bin/python

# always claim to have abdicated already

class oneoff:
    def ready_to_abdicate( self ):
        self.state.set_abdicated()

    def has_abdicated( self ):
        return True
