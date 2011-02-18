#!/usr/bin/env python

class rotator(object):
    def __init__( self, colors=[ '#fcc', '#cfc', '#bbf', '#ffb' ] ):
        self.colors = colors
        self.current_color = 0
    def get_color( self ):
        index = self.current_color
        if index == len( self.colors ) - 1:
            index = 0
        else:
            index += 1
        self.current_color = index
        return self.colors[ index ]
