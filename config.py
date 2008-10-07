#!/usr/bin/python

import logging

# MULTIFLIGHT CONTROLLER CONFIGURATION FILE

# TO DO: DOCUMENT THIS FILE

# logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
#logging_level = logging.INFO
logging_level = logging.DEBUG

dummy_mode = True      
dummy_offset = 24     # how far behind (dummy) real time to start
dummy_rate = 60       # ref time advances 1 hour every 20 seconds
                      # note: task(T)_start - task(T-1)_finish ~20s
                       

# start_time and stop_time must be strings
start_time = "2008080818"
stop_time = "2008081512"

# task_list should be a subset of tasks.all_tasks (defaults to all)
task_list = [ 
        'downloader',
        'nwpglobal',
        'globalprep',
        'globalwave',
        'nzlam',
        'nzlampost',
        'nzwave',
        'ricom',
        'nztide',
        'topnet',
        'mos' 
        ]
