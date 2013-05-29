#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import os
from global_config import gcfg
from rolling_archive import rolling_archive

class dumper( object ):

    def __init__( self, suite, run_mode='live', clock=None, ict=None, stop_tag=None ):
        self.run_mode = run_mode
        self.clock = clock
        self.ict = ict
        self.stop_tag = stop_tag
        self.dir = gcfg.get_derived_host_item( suite, 'suite state directory' )
        self.path = os.path.join( self.dir, 'state' )
        arclen = gcfg.cfg[ 'state dump rolling archive length' ]
        self.archive = rolling_archive( self.path, arclen )

    def set_cts( self, ict, fct ):
        self.ict = ict
        self.stop_tag = fct

    def get_path( self ):
        return self.path

    def get_dir( self ):
        return self.dir

    def dump( self, tasks, wireless, new_file = False ):
        if new_file:
            filename = self.path + '.' + self.clock.dump_to_str()
            FILE = open( filename, 'w' )
        else:
            filename = self.path
            FILE = self.archive.roll()

        # suite time
        if self.run_mode != 'live':
            FILE.write( 'simulation time : ' + self.clock.dump_to_str() + ',' + str( self.clock.get_rate()) + '\n' )
        else:
            FILE.write( 'suite time : ' + self.clock.dump_to_str() + '\n' )

        if self.ict:
            FILE.write( 'initial cycle : ' + self.ict + '\n' )
        else:
            FILE.write( 'initial cycle : (none)\n' )

        if self.stop_tag:
            FILE.write( 'final cycle : ' + self.stop_tag + '\n' )
        else:
            FILE.write( 'final cycle : (none)\n' )

        wireless.dump(FILE)

        FILE.write( 'Begin task states\n' )

        for itask in tasks:
            # TODO - CHECK THIS STILL WORKS 
            itask.dump_class_vars( FILE )
            # task instance variables
            itask.dump_state( FILE )

        FILE.close()
        # return the filename (minus path)
        return os.path.basename( filename )

