#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import os, sys, re
import logging, logging.handlers
from cfgspec.site import sitecfg

"""Configure suite logging with the Python logging module, 'main'
logger, in a sub-directory of the suite running directory."""

class suite_log( object ):
    def __init__( self, suite ):

        self.ldir = sitecfg.get_derived_host_item( suite, 'suite log directory' )
        self.path = os.path.join( self.ldir, 'log' ) 

        self.err_path = os.path.join( self.ldir, 'err' )
        self.roll_at_startup = sitecfg.get( ['suite logging','roll over at start-up'] )
        self.n_keep = sitecfg.get( ['suite logging','rolling archive length'] )
        self.max_bytes = sitecfg.get( ['suite logging','maximum size in bytes'] )

    def get_err_path( self ):
        return self.err_path

    def get_dir( self ):
        return self.ldir

    def get_path( self ):
        return self.path

    def get_log( self ):
        # not really necessary: just get the main logger
        return logging.getLogger( 'main' )

    def pimp( self, level=logging.INFO ):
        log = logging.getLogger( 'main' )
        log.setLevel( level )

        h = logging.handlers.RotatingFileHandler(
                    self.path, 'a', self.max_bytes, self.n_keep )
        # The above creates a zero-sized log file if it doesn't already exist.
        if self.roll_at_startup:
            if os.path.getsize( self.path ) > 0:
                h.doRollover()

        f = logging.Formatter( '%(asctime)s %(levelname)-2s - %(message)s', '%Y/%m/%d %H:%M:%S' )

        # write warnings and worse to stderr as well as to the log
        h2 = logging.StreamHandler(sys.stderr)
        h2.setLevel( logging.WARNING )
        h2.setFormatter( f )
        log.addHandler( h2 )

        h.setFormatter(f)
        log.addHandler(h)

