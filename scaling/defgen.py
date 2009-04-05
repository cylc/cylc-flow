#!/usr/bin/python

import sys

def usage():
    print 'USAGE: ' + sys.argv[0] + ' <n (no. of tasks)'
    sys.exit(1)

def main( argv ):

    if len( argv ) != 2:
        usage()

    n_tasks = argv[1]

    for task in range( 1, int(n_tasks) + 1 ):

        tdef = 'T' + str( task )
        prev_tdef = 'T' + str( task - 1 )

        print "writing task definition file " + str(task)
    
        FILE = open( 'taskdef/' + tdef + '.def', 'w' )
     
        FILE.write(
                """
# THIS IS A SEQUENZ TASK CLASS DEFINITION FILE
# See full_template.def for documented entries

%NAME
""" )
        FILE.write( tdef + '\n' )

        FILE.write(
            """
%VALID_HOURS
    0,6,12,18

%EXTERNAL_TASK
    null

%PREREQUISITES
""")

        if task == 1:
            FILE.write('\n\n')

        else:
            FILE.write( '    ' + prev_tdef + ' finished for $(REFERENCE_TIME)\n' )
            
        FILE.write( 
            """
%POSTREQUISITES
    0 min: $(NAME) started for $(REFERENCE_TIME)
    1 min: $(NAME) finished for $(REFERENCE_TIME)\n""" )
    
        FILE.close() 

    # write config file
    FILE = open( 'config.py', 'w' )

    FILE.write(
            """
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

# DUMMY MODE SETTINGS
dummy_mode = True
dummy_clock_rate = 10      
dummy_clock_offset = 10 

# JOB LAUNCH METHOD
job_launch_method = 'direct'
#job_launch_method = 'qsub'

# LOGGING CONFIGURATION
#logging_dir = os.environ['HOME'] + '/sequenz.logs' 
logging_dir = 'LOGS' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

# STATE DUMP FILE
#state_dump_file = os.environ['HOME'] + '/sequenz.state'
state_dump_file = 'STATE'

# PYRO NAMESERVER CONFIGURATION 
# group must be unique per sequenz instance 
# so that different systems don't interfere
pyro_ns_group = ':scaling'   

task_list = [\n""" )

    for task in range( 1, int(n_tasks) + 1 ):

        tdef = 'T' + str( task )
        FILE.write( '    \'' + tdef + '\',\n' )

    FILE.write(
            """]

# TASKS TO DUMMY OUT IN REAL MODE
# (currently needs to be defined here 
#  as an empty list if not needed)
dummy_out = []
""")

if __name__ == '__main__':
    main( sys.argv )

