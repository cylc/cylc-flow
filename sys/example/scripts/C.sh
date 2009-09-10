#!/bin/bash

# cyclon example system, task C
# depends on task A and its own restart file

# run length 120 minutes, two restart files

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 40 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${REFERENCE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

# ARTIFICIAL ERROR
#[[ $REFERENCE_TIME == 2009082512 ]] && {
#    echo "C: ERROR!!!!!!"
#    exit 1
#}

sleep $SLEEP  # 40 min
touch $TMPDIR/${TASK_NAME}_${NEXT_REFERENCE_TIME}.restart
task-message $TASK_NAME restart files ready for $NEXT_REFERENCE_TIME

sleep $SLEEP  # 80 min
touch $TMPDIR/${TASK_NAME}_${NEXT_NEXT_REFERENCE_TIME}.restart
task-message $TASK_NAME restart files ready for $NEXT_NEXT_REFERENCE_TIME

sleep $SLEEP  # 120 min
OUTPUT=$TMPDIR/C_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready
