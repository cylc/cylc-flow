#!/bin/bash

# cylon example system, task A
# depends on task ext and its own restart file.

# run length 90 minutes, one restart file

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 90 * 60 / ACCEL ))

# check prerequistes
ONE=$TMPDIR/ext_${REFERENCE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, A: $MSG"
        task-message -p CRITICAL $MSG
        task-message -p CRITICAL failed
        exit 1
    }
done

sleep $SLEEP # 90 min

touch $TMPDIR/${TASK_NAME}_${NEXT_REFERENCE_TIME}.restart
task-message $TASK_NAME restart files ready for $NEXT_REFERENCE_TIME

OUTPUT=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready

task-message finished
