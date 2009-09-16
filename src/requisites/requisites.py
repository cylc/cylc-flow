#!/usr/bin/python

# REQUISITES (base class for prerequisites and outputs)
# A collection of messages, each "satisfied" or not.

# NOTE ON LOGGING: Requisite classes have to 'get' the log each time
# logging is required, rather than hold a self.log, because thread
# locking in the logging module is incompatible with 'deep copying' of
# requisites elsewhere in the code (THIS MIGHT NOT APPLY ANYMORE?).

class requisites:
    # A collection of messages, each "satisfied" or not.

    def __init__( self ):
        self.satisfied = {}  # self.satisfied[ "message" ] = True/False

    def count( self ):
        # how many messages are stored
        return len( self.satisfied.keys() )

    def count_satisfied( self ):
        # how many messages are stored
        n = 0
        for message in self.satisfied.keys():
            if self.satisfied[ message ]:
                n += 1
        return n

    def dump( self ):
        # return a string representing each message and its state
        res = []
        for key in self.satisfied.keys():
            res.append( [ key, self.satisfied[ key ] ]  )
        return res

    def all_satisfied( self ):
        if False in self.satisfied.values(): 
            return False
        else:
            return True

    def is_satisfied( self, message ):
        if self.satisfied[ message ]:
            return True
        else:
            return False

    def set_satisfied( self, message ):
        self.satisfied[ message ] = True

    def exists( self, message ):
        if message in self.satisfied.keys():
            return True
        else:
            return False

    def set_all_unsatisfied( self ):
        for message in self.satisfied.keys():
            self.satisfied[ message ] = False

    def set_all_satisfied( self ):
        for message in self.satisfied.keys():
            self.satisfied[ message ] = True

    def get_list( self ):
        return self.satisfied.keys()
