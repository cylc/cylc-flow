#!/bin/bash

# cylc example system, task C
# depends on task A and its own restart file

# run length 120 minutes, two restart files

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 40 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYLC_TIME}.output
TWO=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

# ARTIFICIAL ERROR
#[[ $CYLC_TIME == 2009082512 ]] && {
#    echo "C: ERROR!!!!!!"
#    exit 1
#}

sleep $SLEEP  # 40 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_CYLC_TIME}.restart

sleep $SLEEP  # 80 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_NEXT_CYLC_TIME}.restart

sleep $SLEEP  # 120 min
OUTPUT=$TMPDIR/C_${CYLC_TIME}.output
touch $OUTPUT
