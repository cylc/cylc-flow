#!/usr/bin/python

class sequential:
    # not "ready to abdicate" unless 'finished'.
    def ready_to_abdicate( self ):
        if self.state.has_abdicated():
            return False
        if self.state.is_finished():
            return True
        else:
            return False
