#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SUITE. 
# Task D: postprocess sea state AND storm surge models.

# run length 75 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check prerequisites
ONE=$CYLC_TMPDIR/sea-state-${CYCLE_TIME}.nc
SUBSYS_CYLC_TMPDIR=/tmp/$USER/userguide
TWO=$SUBSYS_CYLC_TMPDIR/storm-surge-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc task-failed "file not found: $PRE"
        exit 1
    fi
done

# EXECUTE THE TASK ...
sleep $(( 75 * 60 / $REAL_TIME_ACCEL ))

# create task outputs
touch $CYLC_TMPDIR/seagram-products-${CYCLE_TIME}.nc
cylc task-message "seagram products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
