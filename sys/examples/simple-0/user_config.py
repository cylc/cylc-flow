#!/usr/bin/python

# cylc user configuration file

# config[ 'item_name' ] = item_value

# see config.py for other options

# DO NOT REMOVE THESE LINES          # !
import logging  # for logging level  # !
import os      # os.environ['HOME']  # !
config = {}                          # !

# USER CONFIGURATION SECTION BEGINS  # !

config[ 'system_name' ] = 'simple-0'

config[ 'logging_dir' ] = os.environ[ 'HOME' ] + '/running/cylc/' + config[ 'system_name' ] + '/log'
config[ 'state_dump_file' ] = os.environ[ 'HOME' ] + '/running/cylc/' + config[ 'system_name' ] + '/state'

config[ 'environment' ] = { 'TMPDIR':'/tmp/' + os.environ['USER'] + '/cylc/' + config[ 'system_name' ] }

config[ 'dummy_mode' ] = False

config[ 'use_qsub' ] = False
config[ 'job_queue' ] = 'default'

config[ 'logging_level' ] = logging.INFO
#config[ 'logging_level' ] = logging.DEBUG

config[ 'max_runahead_hours' ] = 30


config[ 'task_list' ] = \
        [
        'startup',
        'A',
        'B',
        'C',
        'D',
        'E',
        'F'
        ]
