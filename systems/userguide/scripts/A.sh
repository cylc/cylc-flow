#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM,
# Task A: an atmospheric model.

# Depends on real time obs, and own restart file.
# Generates one restart file, valid for the next cycle.

# Run length 90 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# CHECK PREREQUISITES
ONE=$CYLC_TMPDIR/obs-${CYCLE_TIME}.nc
TWO=$CYLC_TMPDIR/${TASK_NAME}-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE MODEL ...
sleep $(( 10 * 60 / $REAL_TIME_ACCEL ))

# create a restart file for the next cycle
touch $CYLC_TMPDIR/${TASK_NAME}-${NEXT_CYCLE_TIME}.restart
cylc message --next-restart-completed

sleep $(( 80 * 60 / $REAL_TIME_ACCEL ))

# create forecast outputs
touch $CYLC_TMPDIR/surface-winds-${CYCLE_TIME}.nc
cylc message "surface wind fields ready for $CYCLE_TIME"

touch $CYLC_TMPDIR/surface-pressure-${CYCLE_TIME}.nc
cylc message "surface pressure field ready for $CYCLE_TIME"

touch $CYLC_TMPDIR/level-fields-${CYCLE_TIME}.nc
cylc message "level forecast fields ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
