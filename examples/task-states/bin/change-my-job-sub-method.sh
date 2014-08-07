#!/bin/bash

EVENT=$1      # e.g. "submit_failed"
SUITE=$2      # name of the suite
TASKID=$3     # ID of the task 
MESSAGE="$4"  # quotes required (message contains spaces)

echo "${0}:resetting job submission method with cylc broadcast"

NAME=${TASKID%.*}
CYCLE=${TASKID#*.}

echo cylc broadcast -n $NAME -t $CYCLE --set "[job submission]method=background" $SUITE
cylc broadcast -n $NAME -t $CYCLE --set "[job submission]method=background" $SUITE
