#!/usr/bin/env python

import gobject
import threading
import tail

class tailer(threading.Thread):
    def __init__( self, logview, log = None ):
        super( tailer, self).__init__()
        self.logview = logview
        self.logbuffer = logview.get_buffer()
        self.logfile = log
        self.quit = False
        self.freeze = False

    def clear( self ):
        s,e = self.logbuffer.get_bounds()
        self.logbuffer.delete( s,e )

    def run( self ):
        gobject.idle_add( self.clear )

        gen = tail.tail( open( self.logfile ))
        while not self.quit:
            if not self.freeze:
                line = gen.next()
                if line: 
                    gobject.idle_add( self.update_gui, line )
        print "Disconnecting from log viewer thread"
 
    def update_gui( self, line ):
        self.logbuffer.insert( self.logbuffer.get_end_iter(), line )
        self.logview.scroll_to_iter( self.logbuffer.get_end_iter(), 0 )
        return False
