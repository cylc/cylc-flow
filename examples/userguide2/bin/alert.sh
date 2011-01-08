#!/bin/bash

# This is an example alert script used by the main example suite.  If
# suite.rc is configured appropriately an alert hook will call the 
# designated script(s) whenever a task is submitted, started, finished,
# failed, or if task job submission fails.

# Cylc supplies the following command line arguments to alert scripts:
# <alert script> HOOK  TASK_NAME  CYCLE_TIME  MESSAGE

# where HOOK is either:
#  'submitted',
#  'started',
#  'finished',
#  'failed', or
#  'submit_failed'

# This script simply prints an alert to stdout (i.e. cylc's stdout). But 
# you can use alert scripts to do whatever you like - e.g. email $USER
# if a task fails; or update a general monitoring system such as Nagios
# according to whether a task has started, finished, or failed, ...

# Put alerting script(s) in your suite bin directory.

HOOK=$1
NAME=$2
CTIME=$3
MESSAGE="$4"  # quotes required: message contains spaces

echo "!!${HOOK}!! $NAME $CTIME $MESSAGE"
