#!/usr/bin/env python


import logging, logging.handlers
import os, sys, re

# NOTE: the dummy mode dummy clock has been replaced with a general
# clock that returns dummy time in dummy mode, so we could replace
# the normal log time universally now... 

class LogFilter(logging.Filter):
    # replace log message timestamps with dummy clock times

    def __init__(self, clock, name = "" ):
        logging.Filter.__init__( self, name )
        self.clock = clock

    def filter(self, record):
        # replace log message time stamp with dummy time
        record.created = self.clock.get_epoch()
        return True
    
def pimp_it( log, dir, level, dummy_mode, clock = None, run_task = False ):
    log.setLevel( level )
    max_bytes = 1000000
    backups = 5
    logfile = dir + '/log'
    if not os.path.exists( dir ):
        raise SystemExit( 'Logging dir ' + dir + ' does not exist' )

    h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
    # The above creates a zero-sized log file if it doesn't already exist.
    # Uncomment the following to get automatic roll over on startup:
    ##if os.path.getsize( logfile ) > 0:
    ##    h.doRollover()

    f = logging.Formatter( '%(asctime)s %(levelname)-2s - %(message)s', '%Y/%m/%d %H:%M:%S' )

    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler( h2 )

    h.setFormatter(f)
    log.addHandler(h)

    if dummy_mode:
        # replace logged real time with dummy clock time 
        log.addFilter( LogFilter( clock, "main" ))
