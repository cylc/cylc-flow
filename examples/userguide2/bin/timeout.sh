#!/bin/bash

# This is an example cylc task timeout script.
# Cylc supplies the following command line arguments:

# <timeout script> HOOK TASK_NAME CYCLE_TIME  MESSAGE

# where HOOK is either:
#  'submission',
#  'execution'

# This script simply prints an alert to stdout (i.e. to cylc's stdout),
# but you can use timeout scripts to do whatever you like - e.g. send an
# email if a task fails; or update a general monitoring system such as
# Nagios.

# Put timeout script(s) in your suite bin directory.

HOOK=$1
NAME=$2
CTIME=$3
MESSAGE="$4"  # quotes required: message contains spaces

echo "!!${HOOK}!! $NAME $CTIME $MESSAGE"
