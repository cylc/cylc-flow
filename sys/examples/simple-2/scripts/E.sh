#!/bin/bash

# cylon example system, task E
# depends on task B

# run length 150 minutes

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 150 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/B_${REFERENCE_TIME}.output
[[ ! -f $PRE ]] && {
    MSG="file not found: $PRE"
    echo "ERROR, E: $MSG"
    task-message -p CRITICAL $MSG
    task-message -p CRITICAL failed
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready

task-message finished
