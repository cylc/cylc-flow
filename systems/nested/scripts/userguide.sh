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
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check prerequisites
ONE=$TMPDIR/surface-winds-${CYCLE_TIME}.nc
TWO=$TMPDIR/surface-pressure-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE MODEL ...
if ! cylc start --at=$CYCLE_TIME --until $CYCLE_TIME userguide; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "subsystem scheduler failed"
    cylc message --failed
    exit 1
fi

cylc message --all-outputs-completed

# SUCCESS MESSAGE
cylc message --succeeded
