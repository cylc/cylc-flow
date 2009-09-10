#!/bin/bash

# cyclon example system, task F
# depends on task C

# run length 50 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/C_${REFERENCE_TIME}.output
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/F_${REFERENCE_TIME}.output
touch $OUTPUT
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME $OUTPUT ready
