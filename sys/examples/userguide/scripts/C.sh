#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task C: a storm surge model.

# Depends on atmos surface pressure and winds, and own restart file.
# Generates two restart files, valid for the next two cycles.

# run length 120 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 40 * 60 / ACCEL )) 

# check prerequistes
ONE=$TMPDIR/A_${CYLC_TIME}.output
TWO=$TMPDIR/${CYLC_TASK}_${CYLC_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file note found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE MODEL ...

# create a restart file for the next cycle
sleep $SLEEP  # 40 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_CYLC_TIME}.restart
cylc message "$CYLC_TASK restart files ready for $NEXT_CYLC_TIME"

# create a restart file for the next next cycle
sleep $SLEEP  # 80 min
touch $TMPDIR/${CYLC_TASK}_${NEXT_NEXT_CYLC_TIME}.restart
cylc message "$CYLC_TASK restart files ready for $NEXT_NEXT_CYLC_TIME"

# create storm surge forecast output
sleep $SLEEP  # 120 min
touch $TMPDIR/storm-surge-forecast-${CYLC_TIME}.nc
cylc message "storm surge fields ready for $CYLC_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
