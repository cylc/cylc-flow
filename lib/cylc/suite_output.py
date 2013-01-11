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

import os, sys
import logging, logging.handlers
from global_config import globalcfg
from rolling_archive import rolling_archive
from mkdir_p import mkdir_p

"""Configure suite stdout and stderr logs, in a sub-directory of the
suite running directory."""

class suite_output( object ):
    def __init__( self, suite ):
        globals = globalcfg()
        self.dir = os.path.join( globals.cfg['run directory'], suite, 'log', 'suite' ) 
        self.opath = os.path.join( self.dir, 'out' ) 
        self.epath = os.path.join( self.dir, 'err' ) 
        self.roll_at_startup = globals.cfg['suite logging']['roll over at start-up']
        try:
            mkdir_p( self.dir )
        except Exception, x:
            # To Do: handle error 
            raise 

        arclen = globals.cfg['suite logging']['rolling archive length']
        self.oarchive = rolling_archive( self.opath, arclen, sep='.' )
        self.earchive = rolling_archive( self.epath, arclen, sep='.' )

    def get_path( self, stderr=False ):
        if stderr:
            return self.epath
        else:
            return self.opath

    def redirect( self ):
        self.roll()
        print "\n Redirecting stdout and stderr (use --no-redirect to prevent this):"
        print ' o stdout:', self.opath
        print ' o stderr:', self.epath
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        # zero sized buffer so output shows up immediately
        sys.stdout = open( self.opath, 'w', 0 )
        sys.stderr = open( self.epath, 'w', 0 )

    def restore( self ):
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        print "\n Restored stdout and stderr to normal"

    def roll( self ):
        self.oarchive.roll()
        self.earchive.roll()

