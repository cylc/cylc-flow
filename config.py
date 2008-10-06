#!/usr/bin/python

# MULTIFLIGHT CONTROLLER CONFIGURATION FILE

# You can define:
#  (1) start_time (string, "YYYYMMHHDD")
#      * can override with the commandline
#  (2) stop_time (string, "YYYYMMHHDD")
#      * defaults to None (i.e. never stop)
#  (3) task_list (list of task name strings, subset of tasks.all_tasks)
#      * defaults to tasks.all_tasks
#  (4) verbosity (string, output level) 
#      * 'NORMAL' all task messages logged, and some controller messages 
#      * 'VERBOSE' for debugging the controller itself 
#      * defaults to 'NORMAL'
#  (5) dummy_mode, dummy_mode_offset, dummy_mode_rate
#      * (TO DO: document dummy mode here)

verbosity = "VERBOSE"

dummy_mode = True
dummy_offset = 3
dummy_rate = 10

# start_time and stop_time must be strings
start_time = "2008080812"
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
