#!/bin/bash

# cylc example system, task B
# depends on task A and its own restart file

# run length 60 minutes, 2 restart files

cylc-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 20 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYCLE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, B: $MSG"
        cylc-message -p CRITICAL $MSG
        cylc-message -p CRITICAL failed
       exit 1
    }
done

sleep $SLEEP   # 20 min
touch $TMPDIR/${TASK_NAME}_${NEXT_CYCLE_TIME}.restart
cylc-message $TASK_NAME restart files ready for $NEXT_CYCLE_TIME

sleep $SLEEP   # 40 min
touch $TMPDIR/${TASK_NAME}_${NEXT_NEXT_CYCLE_TIME}.restart
cylc-message $TASK_NAME restart files ready for $NEXT_NEXT_CYCLE_TIME

sleep $SLEEP   # 60 min
OUTPUT=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $OUTPUT
cylc-message $OUTPUT ready

cylc-message finished
