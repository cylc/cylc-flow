#!/usr/bin/python

# sequenz user configuration file
# see config.py for other options

# DO NOT REMOVE THE FOLLOWING TWO LINES >>>>
import logging  # for logging level
config = {}
####################################### <<<<

config[ 'system_name' ] = 'topnet-dvel'
#config[ 'state_dump_file' ] = 'blah'

config[ 'start_time' ] = '2009052201'
#config[ 'stop_time' ] = '2009030300'

#config[ 'logging_level' ] = logging.INFO
config[ 'logging_level' ] = logging.DEBUG

#config[ 'use_broker' ] = False

config[ 'max_runahead_hours' ] = 24

config[ 'dummy_mode' ] = True
config[ 'dummy_clock_rate' ] = 20
config[ 'dummy_clock_offset' ] = 8

config[ 'use_qsub' ] = False
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
