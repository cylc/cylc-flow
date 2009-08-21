#!/usr/bin/python

# cyclon user configuration file

# config[ 'item_name' ] = item_value

# see config.py for other options

# DO NOT REMOVE THESE LINES          # !
import logging  # for logging level  # !
import os      # os.environ['HOME']  # !
config = {}                          # !

# USER CONFIGURATION SECTION BEGINS  # !

config[ 'system_name' ] = 'example'
config[ 'logging_dir' ] = os.environ[ 'HOME' ] + '/running/cyclon/' + config[ 'system_name' ] + '/log'
config[ 'state_dump_file' ] = os.environ[ 'HOME' ] + '/running/cyclon/' + config[ 'system_name' ] + '/state'

config[ 'dummy_mode' ] = True
config[ 'dummy_clock_rate' ] = 10
config[ 'dummy_clock_offset' ] = 24
config[ 'use_qsub' ] = False
config[ 'job_queue' ] = 'default'

config[ 'start_time' ] = '2009072706'
#config[ 'stop_time'  ] = '2009072806'

config[ 'logging_level' ] = logging.INFO
#config[ 'logging_level' ] = logging.DEBUG

config[ 'max_runahead_hours' ] = 18

config[ 'task_list' ] = \
        [
        'Z',
        'A',
        'B',
        'C',
        'D',
        'E',
        'F'
        ]
