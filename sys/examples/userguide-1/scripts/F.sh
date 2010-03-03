#!/bin/bash

# cylc example system, task F
# depends on task C

# run length 50 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/C_${CYLC_TIME}.output
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

sleep $SLEEP 

OUTPUT=$TMPDIR/F_${CYLC_TIME}.output
touch $OUTPUT
