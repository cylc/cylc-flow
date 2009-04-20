#!/usr/bin/python

# User-editable controller configuration file

# This file gets listed automatically in the latex
# documentation, so keep line lengths reasonable.

import logging
import os

# START AND STOP (OPTIONAL) REFERENCE TIMES
start_time = "2009030200"
stop_time = "2009030300"
#stop_time = None

# DUMMY MODE
dummy_mode = False
dummy_clock_rate = 10      
dummy_clock_offset = 10 

# JOB LAUNCH METHOD
job_launch_method = 'direct'
#job_launch_method = 'qsub'
#job_queue = 'default'

# TOP LEVEL OUTPUT DIR
output_dir = os.environ['HOME'] + '/sequenz-output' 

# LOGGING
logging_dir = output_dir + '/example/log-files' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

# STATE DUMP FILE
state_dump_file = output_dir + '/example/state-dump'

# PYRO NAMESERVER CONFIGURATION 
# group must be unique per sequenz instance 
# so that different systems don't interfere
pyro_ns_group = 'example'   

task_list = [ 'A', 'B', 'C' ]

# TASKS TO DUMMY OUT IN REAL MODE
# (currently needs to be defined here 
#  as an empty list if not needed)
dummy_out = []
