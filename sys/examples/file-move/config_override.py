#!/usr/bin/python

import logging                           # DO NOT DELETE
import os                                # DO NOT DELETE

# THIS CUSTOMIZABLE MODULE CAN BE USED TO OVERRIDE THE CONFIGURATION
# SETTINGS IN config_defaults.py FOR THE SYSTEM DEFINITION DIRECTORY:
# /home/oliverh/cylc/sys/examples/file-move
# IT CAN ALSO BE USED TO SET ADDITIONAL CONFIGURATION ITEMS THAT ARE
# NOT SET IN THE DEFAULTS MODULE: 
# 'task_groups', 'job_submit_overrides', and 'environment'.

# REFER TO THE CYLC USER GUIDE FOR FULL DOCUMENTATION OF CONFIG ITEMS. 

# You may want to consider adding this file to your system definition
# source repository, so that settings here are retained permanently.

# ITEMS THAT ARE SET IN THE DEFAULTS MODULE (add to these as you wish)
config = {}                              # DO NOT DELETE

# DEFAULT JOB SUBMIT METHOD FOR THIS SYSTEM
# value is a string that is the name of a class imported into the
# job_submit_methods module in the system definition directory, e.g.:
#config['job_submit_method'] = 'background2'

# ADDITIONAL ITEMS NOT SET IN THE DEFAULTS MODULE
config['task_groups'] = {}               # DO NOT DELETE
config['job_submit_overrides'] = {}      # DO NOT DELETE
config['environment'] = {}               # DO NOT DELETE

# TASK GROUPS
# Use to insert multiple tasks at once, via 'cylc control', into the
# running system. One use for this item is to group together all tasks
# needed to cold start the system's driving models after a failure that
# prevents continued warm cycling. E.g.:
#config['task_groups']['coldstart'] = [ 'task1', 'task2', 'task3' ]

# ENVIRONMENT VARIABLES FOR USE BY ALL TASKS IN THIS SYSTEM, e.g.:
user_name = os.environ['USER'] 
config['environment']['TMPDIR'] = '/tmp/' + user_name

# OVERRIDE THE DEFAULT JOB SUBMIT METHOD FOR SPECIFIC TASKS, e.g.:
# method names are strings that are the name of a class imported into
# the job_submit_methods module in the system definition directory,
# e.g.:
#config['job_submit_overrides']['background2'] = [ 'task1', 'task2' ]

# END OF FILE 
