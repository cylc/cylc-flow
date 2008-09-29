#!/usr/bin/python

"""
class for printing a spinner to terminal
(user must clear screen in between calls)
"""

class spinner:

    def __init__( self ):
        #self.str = "\|/-"
        self.str = ".oOo"
        self.cindex = 0;

    def spin( self ):
        if self.cindex == 4:
            self.cindex = 0

        foo = self.str[self.cindex]
        self.cindex = self.cindex + 1
        return foo
