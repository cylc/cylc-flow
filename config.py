#!/usr/bin/python
# ECOCONTROLLER CONFIGURATION FILE
import logging

dummy_mode = False
dummy_clock_offset = 8
dummy_clock_rate = 20

pyro_ns_group = ':ecoconnect'

#logging_level = logging.INFO
logging_level = logging.DEBUG

start_time = "2008080812"
stop_time = "2008081012"

dummy_out = []

operational_tasks = [ 
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

topnet_test_tasks = [ 
        'oper2test_topnet',
        'topnet',
        #'topnet_post'
        ]


#task_list = operational_tasks

task_list = topnet_test_tasks
dummy_out = [ 'topnet' ]

