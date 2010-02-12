#!/bin/bash

# cylc example system, task A
# depends on task ext and its own restart file.

# run length 90 minutes, one restart file

cylc-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 90 * 60 / ACCEL ))

# check prerequistes
ONE=$TMPDIR/ext_${CYCLE_TIME}.output
TWO=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, A: $MSG"
        cylc-message -p CRITICAL $MSG
        cylc-message -p CRITICAL failed
        exit 1
    }
done

sleep $SLEEP # 90 min

touch $TMPDIR/${TASK_NAME}_${NEXT_CYCLE_TIME}.restart
cylc-message $TASK_NAME restart files ready for $NEXT_CYCLE_TIME

OUTPUT=$TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $OUTPUT
cylc-message $OUTPUT ready

cylc-message finished
