#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gobject
from tailer import tailer
import os
import re
from cylc import tail
#from warning_dialog import warning_dialog

class filtered_tailer( tailer ):
    def __init__( self, logview, log, filters, tag=None,
            warning_re=None, critical_re=None ):
        self.filters = filters
        tailer.__init__( self, logview, log, tag=tag,
                warning_re=warning_re, critical_re=critical_re )

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
