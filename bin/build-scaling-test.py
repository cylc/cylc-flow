#!/usr/bin/python

import os, sys

def usage():
    print 'USAGE: ' + sys.argv[0] + ' <n (number of tasks)>'
    print 'Generate a system of n interdependent sequenz task definition files,'
    print 'and a sequenz config file to run the system in dummy mode. For use'
    print 'in testing sequenz performance on large task numbers (dummy mode'
    print 'and real mode are the same as far as sequenz is concerned).'
    print ''
    print 'Each task depends only on the previous one, i.e. a simple linear'
    print 'sequence so that only a few external dummy task programs run at once.'
    print 'This prevents the system (hardware, not sequenz) being swamped by a'
    print 'large number of external dummy programs all running at the same time.'
    print ''
    print 'Output locations relative to script running directory:'
    print '  system-def/scaling-test/config.py'
    print '  system-def/scaling-test/taskdef/(task definition files)'
    sys.exit(1)

def main( argv ):

    if len( argv ) != 2:
        usage()

    n_tasks = argv[1]

    topdir = 'system-def/scaling-test'
    defdir = topdir + '/taskdef'

    if not os.path.exists( defdir ):
	print 'creating directory ' + defdir 
	os.makedirs( defdir )

    for task in range( 1, int(n_tasks) + 1 ):

        tdef = 'T' + str( task )
        prev_tdef = 'T' + str( task - 1 )

        print "writing task definition file " + str(task)
    
        FILE = open( defdir + '/' + tdef + '.def', 'w' )
     
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
    FILE = open( topdir + '/config.py', 'w' )

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

# SEQUENCING METHOD: task interaction or negotiation with a broker
#use_broker = False
use_broker = True

# DUMMY MODE
dummy_mode = True
dummy_clock_rate = 10      
dummy_clock_offset = 10 

# JOB LAUNCH METHOD
job_launch_method = 'direct'
#job_launch_method = 'qsub'
#job_queue = 'default'

# TOP LEVEL OUTPUT DIR
output_dir = os.environ['HOME'] + '/sequenz-output' 

# LOGGING
logging_dir = output_dir + '/scaling-test/log-files' 
logging_level = logging.INFO
#logging_level = logging.DEBUG

# STATE DUMP FILE
state_dump_file = output_dir + '/scaling-test/state-dump'

# PYRO NAMESERVER CONFIGURATION 
# group must be unique per sequenz instance 
# so that different systems don't interfere
pyro_ns_group = 'scaling'   

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

