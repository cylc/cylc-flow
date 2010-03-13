#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM.
# Task B: a sea state model.

# Depends on surface wind forecast, and own restart file.
# Generates two restart files, valid for the next two cycles.

# run length 60 minutes, scaled by $REAL_TIME_ACCEL 

# START MESSAGE
cylc message --started

# CHECK PREREQUISITES
ONE=$TMPDIR/surface-winds-${CYCLE_TIME}.nc       # surface winds
TWO=$TMPDIR/${TASK_NAME}-${CYCLE_TIME}.restart   # restart file
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi 
done

# EXECUTE THE MODEL ...

# create a restart file for the next cycle
sleep $(( 20 * 60 / $REAL_TIME_ACCEL ))
touch $TMPDIR/${TASK_NAME}-${NEXT_CYCLE_TIME}.restart
cylc message --next-restart-completed

# create a restart file for the next next cycle
sleep $(( 20 * 60 / $REAL_TIME_ACCEL ))
touch $TMPDIR/${TASK_NAME}-${NEXT_NEXT_CYCLE_TIME}.restart
cylc message --next-restart-completed

# create sea state forecast output
sleep $(( 20 * 60 / $REAL_TIME_ACCEL ))
echo $TMPDIR/sea-state-${CYCLE_TIME}.nc
touch $TMPDIR/sea-state-${CYCLE_TIME}.nc
cylc message "sea state fields ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
