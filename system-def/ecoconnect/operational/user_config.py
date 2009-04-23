#!/usr/bin/python

# sequenz user configuration file
# see config.py for other options

# DO NOT REMOVE THE FOLLOWING TWO LINES >>>>
import logging  # for logging level
config = {}
####################################### <<<<

config[ 'system_name' ] = 'operation'

config[ 'start_time' ] = '2009030200'
#config[ 'stop_time' ] = '2009030300'

config[ 'logging_level' ] = logging.DEBUG

config[ 'use_broker' ] = False

#config[ 'dummy_mode' ] = True
#config[ 'dummy_clock_rate' ] = 10      
#config[ 'dummy_clock_offset' ] = 10 

config[ 'use_qsub' ] = False
config[ 'job_queue' ] = 'oper'

config[ 'task_list' ] = [ 
        'download',
        'nwp_global',
        'global_prep',
        'globalwave',
        'nzlam:finished',
        'nzlam_00_12_post',
        'nzlam_06_18_post',
        'nzwave',
        'ricom',
        'nztide',
        'streamflow',
        'topnet_and_vis',
        'topnet_products',
        'mos' 
        ]
