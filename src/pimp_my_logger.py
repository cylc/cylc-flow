#!/usr/bin/python

import logging, logging.handlers
import config
import os, sys, re

# function to format all task logs in the same way, and to replace
# the message timestamp with dummy clock time in dummy mode.

class LogFilter(logging.Filter):
    # replace log message timestamps with dummy clock times

    def __init__(self, dclock, name = "" ):
        logging.Filter.__init__( self, name )
        self.dummy_clock = dclock

    def filter(self, record):
        # replace log message time stamp with dummy time
        record.created = self.dummy_clock.get_epoch()
        return True
    
def pimp_it( log, name, dummy_clock = None ):
    log.setLevel( config.logging_level )
    max_bytes = 1000000
    backups = 5
    logfile = config.logging_dir + '/' + name
    h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
    # the above creates a zero-sized log file if one doesn't already exist
    if os.path.getsize( logfile ) > 0:
        print ' + rotating existing log:', logfile
        h.doRollover()

    originator = ""
    if name == "main":
        originator = '%(name)-20s'

    f = logging.Formatter( '%(asctime)s %(levelname)-8s ' + originator + ' - %(message)s', '%Y/%m/%d %H:%M:%S' )

    if name == "main":
        # write warnings and worse to stderr as well as to the log
        h2 = logging.StreamHandler(sys.stderr)
        h2.setLevel( logging.WARNING )
        h2.setFormatter( f )
        log.addHandler( h2 )

    h.setFormatter(f)
    log.addHandler(h)

    if config.dummy_mode:
        # replace logged real time with dummy clock time 
        log.addFilter( LogFilter( dummy_clock, "main" ))
