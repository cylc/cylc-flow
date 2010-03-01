#!/usr/bin/python

import logging, logging.handlers
import os, sys, re

# format all task logs in the same way, and in dummy mode replace the
# message timestamp with dummy clock time.

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
    
def pimp_it( log, name, config, dummy_mode, clock = None ):
    log.setLevel( config.get('logging_level') )
    max_bytes = 1000000
    backups = 5
    logfile = config.get('logging_dir') + '/' + name
    h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
    # the above creates a zero-sized log file if one doesn't already exist
    if os.path.getsize( logfile ) > 0:
        #print ' + rotating log:', logfile
        h.doRollover()

    originator = ""
    if name == "main":
        originator = '%(name)-23s'

    f = logging.Formatter( '%(asctime)s %(levelname)-2s ' + originator + ' - %(message)s', '%Y/%m/%d %H:%M:%S' )

    if name == "main":
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
