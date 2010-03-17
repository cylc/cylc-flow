#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task D: postprocess sea state AND storm surge models.

# run length 75 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# check prerequisites
ONE=$TMPDIR/sea-state-${CYCLE_TIME}.nc
TWO=$TMPDIR/storm-surge-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE TASK ...
sleep $(( 75 * 60 / $REAL_TIME_ACCEL ))

# create task outputs
touch $TMPDIR/seagram-products-${CYCLE_TIME}.nc
cylc message "seagram products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
