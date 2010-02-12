#!/bin/bash

# cylc example system, task F
# depends on task C

# run length 50 minutes

cylc-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/C_${CYCLE_TIME}.output
[[ ! -f $PRE ]] && {
    MSG="file not found: $PRE"
    echo "ERROR, F: $MSG"
    cylc-message -p CRITICAL $MSG
    cylc-message -p CRITICAL failed
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/F_${CYCLE_TIME}.output
touch $OUTPUT
cylc-message $OUTPUT ready

cylc-message finished
