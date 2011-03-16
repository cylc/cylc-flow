#!/usr/bin/env python

import gobject
import threading
import os, re
import tail
#from warning_dialog import warning_dialog

class tailer(threading.Thread):
    def __init__( self, logview, log, proc=None, tag=None, format=False ):
        super( tailer, self).__init__()
        self.logview = logview
        self.logbuffer = logview.get_buffer()
        self.logfile = log
        self.quit = False
        self.tag = tag
        self.proc = proc
        self.freeze = False
        self.format = format

    def clear( self ):
        s,e = self.logbuffer.get_bounds()
        self.logbuffer.delete( s,e )

    #def warn( self, message ):
    #    warning_dialog( message ).warn()
    #    return False

    def run( self ):
        #gobject.idle_add( self.clear )
        #print "Starting tailer thread"

        if not os.path.exists( self.logfile ):
            #gobject.idle_add( self.warn, "File not found: " + self.logfile )
            print "File not found: " + self.logfile
            #print "Disconnecting from tailer thread"
            return

        gen = tail.tail( open( self.logfile ))
        while not self.quit:
            if not self.freeze:
                line = gen.next()
                if line:
                    gobject.idle_add( self.update_gui, line )
            # doesn't work:
            #if self.proc != None:
            #    if self.proc.poll() == None:
            #        gobject.idle_add( self.update_gui, '(process completed)\n' )
            #        #break
        
        #print "Disconnecting from tailer thread"
 
    def update_gui( self, line ):
        #if self.format:
        #    if re.match( '.*:', line):
        #        pass
        #    elif re.match( '^\s*$', line):
        #        pass
        #    else:
        #        line = re.sub( r'\n', ' ', line )
        if self.tag:
            self.logbuffer.insert_with_tags( self.logbuffer.get_end_iter(), line, self.tag )
        else:
            self.logbuffer.insert( self.logbuffer.get_end_iter(), line )
        self.logview.scroll_to_iter( self.logbuffer.get_end_iter(), 0 )
        return False
