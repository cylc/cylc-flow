#!/bin/bash

# cyclon example system, task B
# depends on task A and its own restart file

# run length 60 minutes, 2 restart files

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 20 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${REFERENCE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

sleep $SLEEP   # 20 min
touch $TMPDIR/${TASK_NAME}_${NEXT_REFERENCE_TIME}.restart
task-message $TASK_NAME restart files ready for $NEXT_REFERENCE_TIME

sleep $SLEEP   # 40 min
touch $TMPDIR/${TASK_NAME}_${NEXT_NEXT_REFERENCE_TIME}.restart
task-message $TASK_NAME restart files ready for $NEXT_NEXT_REFERENCE_TIME

sleep $SLEEP   # 60 min
OUTPUT=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready
