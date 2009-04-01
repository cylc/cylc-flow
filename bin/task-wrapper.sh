#!/bin/bash

set -e  # abort on error

# load functions
. task-launch/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

#   1. $REFERENCE_TIME  
#   2. $TASK_NAME      
#   3. $WRAP          

if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $WRAP ]]; then
	task_message CRITICAL "WRAP not defined"
	exit 1
fi

echo $TASK_NAME $REFERENCE_TIME

task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

if $WRAP; then 
    task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
else
    task_message CRITICAL "$TASK_NAME FAILED for $REFERENCE_TIME"
fi
