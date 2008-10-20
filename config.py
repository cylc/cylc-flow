#!/usr/bin/python
# ECOCONTROLLER CONFIGURATION FILE
import logging

dummy_mode = True
dummy_clock_offset = 20
dummy_clock_rate = 5

pyro_ns_group = ':ecoconnect'

#logging_level = logging.INFO
logging_level = logging.DEBUG

start_time = "2008080812"
stop_time = "2008080912"

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
