#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task E: postprocess the sea state model.

# run length 150 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 150 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/sea-state-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "file note found: $PRE"
    cylc message --failed
    exit 1
fi

# EXECUTE THE TASK ...
sleep $SLEEP 

# create task outputs
touch $TMPDIR/sea-state-products-${CYCLE_TIME}.nc
cylc message "sea state products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
