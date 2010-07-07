#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task C: storm surge model nested subsuite.

# Depends on atmos surface pressure and winds, and own restart file.
# Generates two restart files, valid for the next two cycles.

# run length 200 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check prerequisites
ONE=$CYLC_TMPDIR/surface-winds-${CYCLE_TIME}.nc
TWO=$CYLC_TMPDIR/surface-pressure-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc task-failed "file not found: $PRE"
        exit 1
    fi
done

# EXECUTE THE MODEL ...
if ! cylc start userguide $CYCLE_TIME --until $CYCLE_TIME; then
    # FAILURE MESSAGE
    cylc task-failed "subsystem scheduler failed"
    exit 1
fi

cylc task-message --all-outputs-completed

# SUCCESS MESSAGE
cylc task-finished
