#!/usr/bin/python

# User-editable controller configuration file

# This file gets listed automatically in the latex
# documentation, so keep line lengths reasonable.

import logging
import os

# START AND STOP (OPTIONAL) REFERENCE TIMES
start_time = "2009030200"
#stop_time = "2009020618"
stop_time = None

# DUMMY MODE SETTINGS
dummy_mode = True
dummy_clock_rate = 10      
dummy_clock_offset = 10 

# JOB LAUNCH METHOD
#job_launch_method = 'qsub'
job_launch_method = 'direct'

# LOGGING CONFIGURATION
logging_dir = os.environ['HOME'] + '/sequenz.logs' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

# STATE DUMP FILE
state_dump_file = os.environ['HOME'] + '/sequenz.state'

# PYRO NAMESERVER CONFIGURATION 
# group must be unique per sequenz instance 
# so that different systems don't interfere
pyro_ns_group = 'operational'   

# TASK LIST 
task_list = [ 
        'download',
        'nwp_global',
        'global_prep',
        'globalwave',
        'nzlam:finished',
        'nzlam_00_12_post',
        'nzlam_06_18_post',
        'nzwave',
        'ricom',
        'nztide',
        'streamflow',
        'topnet_and_vis',
        'topnet_products',
        'mos' 
        ]

# TASKS TO DUMMY OUT IN REAL MODE
# (currently needs to be defined 
#  as an empty list if not needed)
dummy_out = []
