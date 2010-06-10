#!/usr/bin/env python

import threading
import tail

class tailer(threading.Thread):
    def __init__( self, gobject, logview, log = None ):
        super( tailer, self).__init__()
        self.gobject = gobject
        self.logview = logview
        self.logbuffer = logview.get_buffer()
        self.logfile = log
        self.quit = False
        self.freeze = False
        self.gobject.idle_add( self.update_gui, 'WAITING' )

    def run( self ):
        if self.logfile == None:
            return

        gen = tail.tail( open( self.logfile ))
        while not self.quit:
            if not self.freeze:
                line = gen.next()
                if line: 
                    self.gobject.idle_add( self.update_gui, line )
        print "Disconnecting from log viewer thread"
 
    def update_gui( self, line ):
        self.logbuffer.insert( self.logbuffer.get_end_iter(), line )
        self.logview.scroll_to_iter( self.logbuffer.get_end_iter(), 0 )
        return False
