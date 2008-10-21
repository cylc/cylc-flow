#!/usr/bin/python

import logging

# THE FOLLOWING ITEMS MUST BE DEFINED IN THIS CONFIGURATION FILE:

#  1. start_time ('yyyymmddhh')
#  2. stop_time  ('yyyymmddhh', or None for no stop)
#  3. dummy_mode (dummy out all tasks)
#  4. dummy_clock_rate (seconds per simulated hour) 
#  5. dummy_clock_offset (hours before start_time)
#  6. task_list (tasks out of task_definitions module to run)
#  7. dummy_out (tasks to dummy out even when dummy_mode is False)
#  8. logging_dir (directory under which to put all log files)
#  9. logging_level (logging.INFO or logging.DEBUG)
# 10. pyro_ns_group (must be unique for each running controller)
# 11. state_dump_file (records current system state)

dummy_mode = True
dummy_clock_offset = 20
dummy_clock_rate = 5

logging_dir = 'LOGFILES'
state_dump_file = 'STATE'

pyro_ns_group = ':ecoconnect'

#logging_level = logging.INFO
logging_level = logging.DEBUG

start_time = "2008102012"
stop_time = "2008202200"

dummy_out = []

operational_tasks = [ 
        'downloader',
        'nwp_global',
        'global_prep',
        'globalwave',
        'nzlam:finished',
        'nzlam_post',
        'nzwave',
        'ricom',
        'nztide',
        'topnet',
        'mos' 
        ]

topnet_test_tasks = [ 
        'oper2test_topnet',
        'topnet',
        #'topnet_post'
        ]

task_list = operational_tasks
#task_list = topnet_test_tasks
#dummy_out = [ 'topnet' ]
