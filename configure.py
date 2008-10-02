#!/usr/bin/python

# MULTIFLIGHT CONTROLLER CONFIGURATION FILE

# You can define:
#  (1) start_time (string, "YYYYMMHHDD")
#      * can override with the commandline
#  (2) stop_time (string, "YYYYMMHHDD")
#      * defaults to None (i.e. never stop)
#  (3) task_list (list of string task names, subset of tasks.all_tasks)
#      * defaults to tasks.all_tasks

# start_time and stop_time must be strings
start_time = "2008080806"
stop_time = "2008080812"

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
