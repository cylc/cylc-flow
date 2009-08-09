#!/usr/bin/python

# sequenz user configuration file

# config[ 'item_name' ] = item_value

# see config.py for other options

# DO NOT REMOVE THESE LINES          # !
import logging  # for logging level  # !
import os      # os.environ['HOME']  # !
config = {}                          # !

# USER CONFIGURATION SECTION BEGINS  # !

config[ 'system_name' ] = 'topnet-test'
config[ 'logging_dir' ] = os.environ[ 'HOME' ] + '/' + config[ 'system_name' ] + '/log'
config[ 'state_dump_file' ] = os.environ[ 'HOME' ] + '/' + config[ 'system_name' ] + '/state'

config[ 'dummy_mode' ] = True
config[ 'use_qsub' ] = False

config[ 'start_time' ] = '2009072706'
#config[ 'stop_time'  ] = '2009072806'

#config[ 'logging_level' ] = logging.INFO
config[ 'logging_level' ] = logging.DEBUG

config[ 'max_runahead_hours' ] = 48

config[ 'job_queue' ] = 'topnet_test'

config[ 'task_list' ] = \
        [
        'oper_interface',
        'streamflow',
        'topnet',
        'topnet_vis',
        'topnet_products',
        'topnet_cleanup'
        ]
