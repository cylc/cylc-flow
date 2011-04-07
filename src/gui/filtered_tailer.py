#!/usr/bin/env python

import gobject
from tailer import tailer
import os
import re
import tail
#from warning_dialog import warning_dialog

class filtered_tailer( tailer ):
    def __init__( self, logview, log, filters ):
        self.filters = filters
        tailer.__init__( self, logview, log )

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
                    match = True
                    for filter in self.filters:
                        if filter:
                            if not re.search( filter, line ):
                                match = False 
                                break
                    if match:
                        gobject.idle_add( self.update_gui, line )
        ###print "Disconnecting from log viewer thread"
