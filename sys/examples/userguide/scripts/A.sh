#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM,
# Task A: an atmospheric model.

# Depends on real time obs, and own restart file.
# Generates one restart file, valid for the next cycle.

# Run length 90 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP1=$(( 10 * 60 / ACCEL ))
SLEEP2=$(( 80 * 60 / ACCEL ))

# CHECK PREREQUISITES
ONE=$TMPDIR/obs-${CYCLE_TIME}.nc
TWO=$TMPDIR/${TASK_NAME}-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file note found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE MODEL ...
sleep $SLEEP1

# create a restart file for the next cycle
touch $TMPDIR/${TASK_NAME}-${NEXT_CYCLE_TIME}.restart
cylc message "$TASK_NAME restart files ready for $NEXT_CYCLE_TIME"

sleep $SLEEP2

# create forecast outputs
touch $TMPDIR/surface-winds-${CYCLE_TIME}.nc
cylc message "surface wind fields ready for $CYCLE_TIME"

touch $TMPDIR/surface-pressure-${CYCLE_TIME}.nc
cylc message "surface pressure field ready for $CYCLE_TIME"

touch $TMPDIR/level-fields-${CYCLE_TIME}.nc
cylc message "level forecast fields ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
