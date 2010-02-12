#!/bin/bash

# cylc example system, task E
# depends on task B

# run length 150 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 150 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/B_${CYCLE_TIME}.output
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $OUTPUT
