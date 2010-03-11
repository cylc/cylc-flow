#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task F: postprocess the storm surge model.

# run length 50 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/storm-surge-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "file note found: $PRE"
    cylc message --failed
    exit 1
fi

# EXECUTE THE TASK ...
sleep $SLEEP 

touch $TMPDIR/storm-surge-products-${CYCLE_TIME}.nc
cylc message "storm surge products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
