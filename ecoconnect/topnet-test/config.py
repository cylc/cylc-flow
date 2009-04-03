#!/usr/bin/python

# User-editable controller configuration file

# This file gets listed automatically in the latex
# documentation, so keep line lengths reasonable.

import logging
import os

# START AND STOP (OPTIONAL) REFERENCE TIMES
start_time = "2009032618"
#stop_time = "2009032718"
stop_time = None

# DUMMY MODE SETTINGS
dummy_mode = False
dummy_clock_rate = 10      
dummy_clock_offset = 10 

#job_launch_method = 'direct'
job_launch_method = 'qsub'

# LOGGING CONFIGURATION
logging_dir = os.environ['HOME'] + '/running/topnet_test/log' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

# STATE DUMP FILE
state_dump_file = os.environ['HOME'] + '/running/topnet_test/state'

# PYRO NAMESERVER CONFIGURATION 
# group must be unique per sequenz instance 
# so that different systems don't interfere
pyro_ns_group = ':topnet_test'   

# TASK LIST 
task_list = [ 
        'oper2test_topnet',
        'streamflow',
        'topnet_and_vis',
        'topnet_products'
        ]

# TASKS TO DUMMY OUT IN REAL MODE
# (currently needs to be defined 
#  as an empty list if not needed)
dummy_out = []
#dummy_out = [ 'topnet_and_vis' ]
