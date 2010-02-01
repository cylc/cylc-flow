#!/bin/bash

# cylc example system, task D
# depends on tasks B and C

# run length 75 minutes

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 75 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/B_${REFERENCE_TIME}.output
TWO=$TMPDIR/C_${REFERENCE_TIME}.output
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, D: $MSG"
        task-message -p CRITICAL $MSG
        task-message -p CRITICAL failed
        exit 1
    }
done

sleep $SLEEP   # 75 min

OUTPUT=$TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
touch $OUTPUT
task-message $OUTPUT ready

task-message finished
