#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

cylc task-started || exit 1

COUNT=0

PLATFORM=$( uname -n )

while (( COUNT < 10 )); do
    cylc task-message "$COUNT - hello from $PLATFORM"
    COUNT=$(( COUNT + 1 ))
    sleep 1
done

cylc task-message "remote platform processing completed for $CYCLE_TIME"
cylc task-finished
