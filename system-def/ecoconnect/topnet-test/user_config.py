#!/usr/bin/python

# sequenz user configuration file
# see config.py for other options

# DO NOT REMOVE THE FOLLOWING TWO LINES >>>>
import logging  # for logging level
config = {}
####################################### <<<<

config[ 'system_name' ] = 'topnet-test'

config[ 'start_time' ] = '2009071206'
config[ 'stop_time'  ] = '2009072606'

#config[ 'logging_level' ] = logging.INFO
config[ 'logging_level' ] = logging.DEBUG

#config[ 'use_broker' ] = False

config[ 'max_runahead_hours' ] = 48

config[ 'restrict_unconstrained_tasks' ] = False

config[ 'dummy_mode' ] = False
config[ 'use_qsub' ] = True
config[ 'dummy_clock_rate' ] = 20
config[ 'dummy_clock_offset' ] = 100

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
