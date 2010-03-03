#!/bin/bash

# cylc example system, task A
# depends on task ext and its own restart file.

# run length 90 minutes, one restart file

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 90 * 60 / ACCEL ))

# check prerequistes
ONE=$TMPDIR/ext_${CYLC_TIME}.output
TWO=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, A: $MSG"
        exit 1
    }
done

sleep $SLEEP # 90 min

touch $TMPDIR/${CYLC_TASK}_${NEXT_CYLC_TIME}.restart

OUTPUT=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.output
touch $OUTPUT
