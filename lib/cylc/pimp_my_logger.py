#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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


import logging, logging.handlers
import os, sys, re

class LogFilter(logging.Filter):
    # Replace log timestamps with those of the supplied clock
    # (which may be UTC or simulation time).
    def __init__(self, clock, name = "" ):
        logging.Filter.__init__( self, name )
        self.clock = clock

    def filter(self, record):
        # replace log message time stamp with simulation time
        record.created = self.clock.get_epoch()
        return True
    
def pimp_it( log, dir, roll_at_startup, level, clock ):
    log.setLevel( level )
    max_bytes = 1000000
    backups = 5
    logfile = dir + '/log'
    if not os.path.exists( dir ):
        raise SystemExit( 'Logging dir ' + dir + ' does not exist' )

    h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
    # The above creates a zero-sized log file if it doesn't already exist.
    if roll_at_startup:
        if os.path.getsize( logfile ) > 0:
            h.doRollover()

    f = logging.Formatter( '%(asctime)s %(levelname)-2s - %(message)s', '%Y/%m/%d %H:%M:%S' )

    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler( h2 )

    h.setFormatter(f)
    log.addHandler(h)

    # replace default time stamps
    if clock:
        log.addFilter( LogFilter( clock, "main" ))
