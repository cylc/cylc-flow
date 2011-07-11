#!/bin/bash

# This is an example cylc alert script.
# Cylc supplies the following command line arguments:

# <alert script> EVENT  TASK_NAME  CYCLE_TIME  MESSAGE

# where EVENT is either:
#  'submitted',
#  'started',
#  'finished',
#  'failed', or
#  'submit_failed'

# This script simply prints an alert to stdout (i.e. to cylc's stdout),
# but you can use alert scripts to do whatever you like - e.g. send an
# email if a task fails; or update a general monitoring system such as
# Nagios according to whether a task has started, finished, or failed.

EVENT=$1
NAME=$2
CTIME=$3
MESSAGE="$4"  # quotes required: message contains spaces

echo "!!${EVENT}!! $NAME $CTIME $MESSAGE"
