#!/bin/bash

# cylc example system, task E
# depends on task B

# run length 150 minutes

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 150 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/B_${CYCLE_TIME}.output
[[ ! -f $PRE ]] && {
    MSG="file not found: $PRE"
    echo "ERROR, E: $MSG"
    cylc message -p CRITICAL $MSG
    cylc message --failed
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $OUTPUT
cylc message "$OUTPUT ready"

cylc message --succeeded
