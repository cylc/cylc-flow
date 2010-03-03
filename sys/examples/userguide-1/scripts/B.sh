#!/bin/bash

# cylc example system, task B
# depends on task A and its own restart file

# run length 60 minutes, 2 restart files

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 20 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYLC_TIME}.output
TWO=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

sleep $SLEEP   # 20 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_CYLC_TIME}.restart

sleep $SLEEP   # 40 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_NEXT_CYLC_TIME}.restart

sleep $SLEEP   # 60 min
OUTPUT=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.output
touch $OUTPUT
