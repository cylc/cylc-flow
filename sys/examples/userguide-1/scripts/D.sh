#!/bin/bash

# cylc example system, task D
# depends on tasks B and C

# run length 75 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 75 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/B_${CYCLE_TIME}.output
TWO=$TMPDIR/C_${CYCLE_TIME}.output
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

sleep $SLEEP   # 75 min

OUTPUT=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $OUTPUT
