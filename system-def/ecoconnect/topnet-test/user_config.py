#!/usr/bin/python

# sequenz user configuration file
# see config.py for other options

# DO NOT REMOVE THE FOLLOWING TWO LINES >>>>
import logging  # for logging level
config = {}
####################################### <<<<

config[ 'system_name' ] = 'topnet-test'
#config[ 'state_dump_file' ] = 'blah'

config[ 'start_time' ] = '2009030200'
#config[ 'stop_time' ] = '2009030300'

config[ 'logging_level' ] = logging.INFO

#config[ 'use_broker' ] = False

config[ 'dummy_mode' ] = False
config[ 'dummy_clock_rate' ] = 10
config[ 'dummy_clock_offset' ] = 10 

config[ 'use_qsub' ] = True
config[ 'job_queue' ] = 'topnet_test'

config[ 'task_list' ] = [ 
        'oper2test_topnet',
        'streamflow',
        'topnet_and_vis',
        'topnet_products',
        'cleanup_topnet_nc'
        ]
