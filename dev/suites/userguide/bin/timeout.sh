#!/bin/bash

# This is an example cylc task timeout script.
# Cylc supplies the following command line arguments:

# <timeout script> EVENT TASK_NAME CYCLE_TIME MESSAGE

# where EVENT is either:
#  'submission'  # task timed out in job submission
#  'execution'   # task timed out in execution

# MESSAGE contains the timeout value, e.g.:
#   "submitted 12 minutes ago, but has not started"
#   "started 23 minutes ago, but has not finished"

# This script simply prints an alert to stdout (i.e. to cylc's stdout),
# but you can use timeout scripts to do whatever you like - e.g. send an
# email if a task fails; or update a general monitoring system such as
# Nagios.

EVENT=$1
NAME=$2
CTIME=$3
MESSAGE="$4"  # quotes required: message contains spaces

echo "!!${EVENT}!! $NAME $CTIME $MESSAGE"
