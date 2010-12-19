#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM Task A IMPLEMENTATION.

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check environment
check-env.sh || exit 1

# CHECK PREREQUISITES
ONE=$CYLC_TMPDIR/obs-${CYCLE_TIME}.nc
TWO=$CYLC_TMPDIR/${TASK_NAME}-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc task-failed "file not found: $PRE"
        exit 1
    fi
done

# EXECUTE THE MODEL ...
NEXT_CYCLE=$(cylcutil cycle-time -a 6)

# create a restart file for the next cycle
sleep $(( TASK_RUN_TIME_SECONDS / 2 ))
touch $CYLC_TMPDIR/${TASK_NAME}-${NEXT_CYCLE}.restart
cylc task-message --next-restart-completed

# create forecast outputs
sleep $(( TASK_RUN_TIME_SECONDS / 2 ))
touch $CYLC_TMPDIR/surface-winds-${CYCLE_TIME}.nc
cylc task-message "surface wind fields ready for $CYCLE_TIME"

touch $CYLC_TMPDIR/surface-pressure-${CYCLE_TIME}.nc
cylc task-message "surface pressure field ready for $CYCLE_TIME"

touch $CYLC_TMPDIR/level-fields-${CYCLE_TIME}.nc
cylc task-message "level forecast fields ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
