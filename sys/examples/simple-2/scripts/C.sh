#!/bin/bash

# cylc example system, task C
# depends on task A and its own restart file

# run length 120 minutes, two restart files

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 40 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYCLE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.restart
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
#[[ $CYCLE_TIME == 2009082512 ]] && {
#    echo "C: ERROR!!!!!!"
#    exit 1
#}

sleep $SLEEP  # 40 min
touch $TMPDIR/${TASK_NAME}_${NEXT_CYCLE_TIME}.restart
cylc message "$TASK_NAME restart files ready for $NEXT_CYCLE_TIME"

sleep $SLEEP  # 80 min
touch $TMPDIR/${TASK_NAME}_${NEXT_NEXT_CYCLE_TIME}.restart
cylc message "$TASK_NAME restart files ready for $NEXT_NEXT_CYCLE_TIME"

sleep $SLEEP  # 120 min
OUTPUT=$TMPDIR/C_${CYCLE_TIME}.output
touch $OUTPUT
cylc message "$OUTPUT ready"

cylc message --succeeded
