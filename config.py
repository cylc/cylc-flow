#!/usr/bin/python

import logging

# MULTIFLIGHT CONTROLLER CONFIGURATION FILE

# TO DO: DOCUMENT THIS FILE

# logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
#logging_level = logging.INFO
logging_level = logging.DEBUG

dummy_mode = True      
dummy_offset = 24     # how far behind (dummy) real time to start
dummy_rate = 60       # must be included: read by task_dummy

# start_time and stop_time must be strings
start_time = "2008080818"
stop_time = "2008081512"

# task_list should be a subset of tasks.all_tasks (defaults to all)
# optional initial states: 'finishd', 'ready', 'waiting' (default)
task_list = [ 
        'downloader',
        'nwpglobal',
        'globalprep',
        'globalwave',
        'nzlam:finishd',
        'nzlam_post:ready',
        'nzwave',
        'ricom',
        'nztide',
        'topnet',
        'mos' 
        ]
