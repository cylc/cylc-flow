#!/usr/bin/python

import logging

# MULTIFLIGHT CONTROLLER CONFIGURATION FILE

# TO DO: DOCUMENT THIS FILE

# pyro nameserver group (must be different for each control program instance)
pyro_ns_group = ':ecoconnect'

# which task class definition module to use
task_module = 'topnet_test_task_defs'

# logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging_level = logging.INFO
#logging_level = logging.DEBUG

dummy_mode = True      
dummy_offset = 8    # how far behind (dummy) real time to start
dummy_rate = 20

# start_time and stop_time must be strings
start_time = "2008080818"
stop_time = "2008081512"

# task_list optional initial states: 'finished', 'ready', 'waiting'
# (default is 'waiting')
task_list = [ 
        'nzlam_post',
        'topnet',
        #'topnet_post'
        ]
