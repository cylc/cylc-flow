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
# Task E: postprocess the sea state model.

# run length 15 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# check prerequisites
PRE=$CYLC_TMPDIR/sea-state-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "file not found: $PRE"
    cylc message --failed
    exit 1
fi

# EXECUTE THE TASK ...
sleep $(( 15 * 60 / $REAL_TIME_ACCEL ))

# create task outputs
touch $CYLC_TMPDIR/sea-state-products-${CYCLE_TIME}.nc
cylc message "sea state products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
