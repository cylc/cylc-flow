#!/usr/bin/python

# GLOBAL CONFIGURATION FILE

import logging

dummy_mode = True
dummy_clock_offset = 8
dummy_clock_rate = 20

#logging_level = logging.INFO
logging_level = logging.DEBUG

start_time = "2008080818"
stop_time = "2008081012"

operational_task_defs = 'operational_tasks'
operational_task_list = [ 
        'downloader',
        'nwpglobal',
        'globalprep',
        'globalwave',
        'nzlam:finished',
        'nzlam_post',
        'nzwave',
        'ricom',
        'nztide',
        'topnet',
        'mos' 
        ]

topnet_test_task_defs = 'topnet_test_tasks'
topnet_upstream_task = 'oper2test_topnet'
topnet_test_task_list = [ 
        'oper2test_topnet',
        'topnet',
        #'topnet_post'
        ]

pyro_ns_group = ':ecoconnect'   # see pyro_ns_naming.py

task_module = operational_task_defs
#task_list = operational_task_list

#task_module = topnet_test_task_defs
task_list = topnet_test_task_list
