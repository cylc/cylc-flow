#!/bin/bash

# cyclon example system, task E
# depends on task B

# run length 150 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 150 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/B_${REFERENCE_TIME}.output
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
touch $OUTPUT
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME $OUTPUT ready
