#!/usr/bin/env python

import gobject
import threading
import os
import tail
#from warning_dialog import warning_dialog

class tailer(threading.Thread):
    def __init__( self, logview, log ):
        super( tailer, self).__init__()
        self.logview = logview
        self.logbuffer = logview.get_buffer()
        self.logfile = log
        self.quit = False
        self.freeze = False

    def clear( self ):
        s,e = self.logbuffer.get_bounds()
        self.logbuffer.delete( s,e )

    #def warn( self, message ):
    #    warning_dialog( message ).warn()
    #    return False

    def run( self ):
        #gobject.idle_add( self.clear )

        if not os.path.exists( self.logfile ):
            #gobject.idle_add( self.warn, "File not found: " + self.logfile )
            #print "File not found: " + self.logfile
            ###print "Disconnecting from log viewer thread"
            return

        gen = tail.tail( open( self.logfile ))
        while not self.quit:
            if not self.freeze:
                line = gen.next()
                if line:
                    gobject.idle_add( self.update_gui, line )
        ###print "Disconnecting from log viewer thread"
 
    def update_gui( self, line ):
        self.logbuffer.insert( self.logbuffer.get_end_iter(), line )
        self.logview.scroll_to_iter( self.logbuffer.get_end_iter(), 0 )
        return False
