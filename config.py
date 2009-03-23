#!/usr/bin/python

# User-editable controller configuration file

# This file gets listed automatically in the latex
# documentation, so keep line lengths reasonable.

import logging

# dummy mode settings
dummy_mode = True
dummy_clock_rate = 10      
dummy_clock_offset = 0 
dummy_job_launch = 'direct'
#dummy_job_launch = 'qsub'

# logging 
logging_dir = 'LOGFILES' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

state_dump_file = 'STATE'

# pyro nameserver group must be unique per controller
# instance so that different programs don't interfere.
pyro_ns_group = ':foo'   

# start and (optional) stop reference times
start_time = "2009030200"
#stop_time = "2009020618"
stop_time = None

# list the tasks to run
operational_tasks = [ 
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

operational_task_launch_dir = 'task-launch/ecoconnect-operations'

topnet_test_tasks = [ 
        'oper2test_topnet',
        'streamflow',
        'topnet_and_vis',
        'topnet_products'
        ]

topnet_test_task_launch_dir = 'task-launch/topnet-hourly-testing'

#task_list = operational_tasks
#task_launch_dir = operational_task_launch_dir 

task_list = topnet_test_tasks
task_launch_dir = topnet_test_task_launch_dir

# list tasks to dummy out in real mode
# (currently needs to be defined as an empty list if not needed)
dummy_out = []
#dummy_out = [ 'topnet_and_vis' ]
