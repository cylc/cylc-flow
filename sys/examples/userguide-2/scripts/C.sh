#!/bin/bash

# cylc example system, task C
# depends on task A and its own restart file

# run length 120 minutes, two restart files

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 40 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYLC_TIME}.output
TWO=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, C: $MSG"
        cylc message -p CRITICAL $MSG
        cylc message --failed
        exit 1
    }
done

# ARTIFICIAL ERROR
#[[ $CYLC_TIME == 2009082512 ]] && {
#    echo "C: ERROR!!!!!!"
#    exit 1
#}

sleep $SLEEP  # 40 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_CYLC_TIME}.restart
cylc message "$CYLC_TASK restart files ready for $NEXT_CYLC_TIME"

sleep $SLEEP  # 80 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_NEXT_CYLC_TIME}.restart
cylc message "$CYLC_TASK restart files ready for $NEXT_NEXT_CYLC_TIME"

sleep $SLEEP  # 120 min
OUTPUT=$TMPDIR/C_${CYLC_TIME}.output
touch $OUTPUT
cylc message "$OUTPUT ready"

cylc message --succeeded
