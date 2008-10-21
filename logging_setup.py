#!/usr/bin/python

import logging, logging.handlers
import config
import os, sys, re

from log_filter import *

def pimp_my_logger( log, name, dummy_clock = None ):
    log.setLevel( config.logging_level )
    max_bytes = 1000000
    backups = 5
    logfile = 'LOGFILES/' + name
    h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
    # the above creates a zero-sized log file if one doesn't already exist
    if os.path.getsize( logfile ) > 0:
        print ' + rotating existing log:', logfile
        h.doRollover()

    f = logging.Formatter( '%(asctime)s %(levelname)-8s %(name)-16s - %(message)s', '%Y/%m/%d %H:%M:%S' )
    # use '%(name)-30s' to get the logger name print too 
    h.setFormatter(f)
    log.addHandler(h)

    # write warnings and worse to stderr as well as to the log
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel( logging.WARNING )
    h2.setFormatter( f )
    log.addHandler(h2)
    if config.dummy_mode:
        # replace logged real time with dummy clock time 
        log.addFilter( LogFilter( dummy_clock, "main" ))
