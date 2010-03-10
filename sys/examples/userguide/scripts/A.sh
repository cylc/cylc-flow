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
ONE=$TMPDIR/atmos-obs-${CYLC_TIME}.nc
TWO=$TMPDIR/atmos-${CYLC_TIME}.restart
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
touch $TMPDIR/atmos-${NEXT_CYLC_TIME}.restart
cylc message "$CYLC_TASK restart files ready for $NEXT_CYLC_TIME"

sleep $SLEEP2

# create forecast outputs
touch $TMPDIR/surface-winds-${CYLC_TIME}.nc
cylc message "surface wind fields ready for $CYLC_TIME"

touch $TMPDIR/surface-pressure-${CYLC_TIME}.nc
cylc message "surface pressure field ready for $CYLC_TIME"

touch $TMPDIR/model-level-fields-${CYLC_TIME}.nc
cylc message "model level forecast fields ready for $CYLC_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
