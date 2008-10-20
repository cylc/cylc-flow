#!/usr/bin/python

import logging, logging.handlers
import config
import os, sys, re

from log_filter import *

def setup_logging( dummy_clock ):

    print
    print 'Logging to ' + config.logging_dir

    if not os.path.exists( config.logging_dir ):
        os.makedirs( config.logging_dir )

    log = logging.getLogger( "main" )
    log.setLevel( config.logging_level )
    max_bytes = 1000000
    backups = 5
    main_logfile = 'LOGFILES/ecocontroller'
    h = logging.handlers.RotatingFileHandler( main_logfile, 'a', max_bytes, backups )
    # the above creates a zero-sized log file if one doesn't already exist
    if os.path.getsize( main_logfile ) > 0:
        print ' + rotating existing log:', main_logfile
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

    # task-name-specific log files for all tasks 
    # these propagate messages up to the main log
    for name in config.task_list:
        if re.compile( "^.*:").match( name ):
            [name, state] = name.split( ':' )
        foo = logging.getLogger( "main." + name )
        foo.setLevel( config.logging_level )

        task_logfile = 'LOGFILES/' + name
        h = logging.handlers.RotatingFileHandler( task_logfile, 'a', max_bytes/10, backups )
        # the above creates a zero-sized log file if one doesn't already exist
        if os.path.getsize( task_logfile ) > 0:
            print ' + rotating existing log:', task_logfile
            h.doRollover()

        f = logging.Formatter( '%(asctime)s %(levelname)-8s - %(message)s', '%Y/%m/%d %H:%M:%S' )
        h.setFormatter(f)
        foo.addHandler(h)
        if config.dummy_mode:
            # replace logged real time with dummy clock time 
            foo.addFilter( LogFilter( dummy_clock, "main" ))
