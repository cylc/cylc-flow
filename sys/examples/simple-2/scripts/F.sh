#!/bin/bash

# cylc example system, task F
# depends on task C

# run length 50 minutes

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/C_${REFERENCE_TIME}.output
[[ ! -f $PRE ]] && {
    MSG="file not found: $PRE"
    echo "ERROR, F: $MSG"
    task-message -p CRITICAL $MSG
    task-message -p CRITICAL failed
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/F_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready

task-message finished
