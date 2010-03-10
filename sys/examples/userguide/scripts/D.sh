#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task D: postprocess sea state AND storm surge models.

# run length 75 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 75 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/sea-state-${CYLC_TIME}.nc
TWO=$TMPDIR/storm-surge-${CYLC_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file note found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE TASK ...
sleep $SLEEP

# create task outputs
touch $TMPDIR/seagram-products-${CYLC_TIME}.nc
cylc message "seagram products ready for $CYLC_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
