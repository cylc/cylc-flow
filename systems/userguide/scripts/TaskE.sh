#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM Task E IMPLEMENTATION.

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check environment
check-env.sh || exit 1

# check prerequisites
PRE=$CYLC_TMPDIR/sea-state-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE MESSAGE
    cylc task-failed "file not found: $PRE"
    exit 1
fi

# EXECUTE THE TASK ...
sleep $TASK_RUN_TIME_SECONDS

# create task outputs
touch $CYLC_TMPDIR/sea-state-products-${CYCLE_TIME}.nc
cylc task-message "sea state products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
