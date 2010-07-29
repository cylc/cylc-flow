#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM Task C IMPLEMENTATION.

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check environment
check-env.sh || exit 1

# check prerequisites
ONE=$CYLC_TMPDIR/surface-winds-${CYCLE_TIME}.nc
TWO=$CYLC_TMPDIR/surface-pressure-${CYCLE_TIME}.nc
THR=$CYLC_TMPDIR/${TASK_NAME}-${CYCLE_TIME}.restart
for PRE in $ONE $TWO $THR; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc task-failed "file not found: $PRE"
        exit 1
    fi
done

# EXECUTE THE MODEL ...
NEXT_CYCLE=$(cylcutil time-calc -a 6)
NEXT_NEXT_CYCLE=$(cylcutil time-calc -a 12)

# create a restart file for the next cycle
sleep $(( TASK_RUN_TIME_SECONDS / 3 ))
touch $CYLC_TMPDIR/${TASK_NAME}-${NEXT_CYCLE}.restart
cylc task-message --next-restart-completed

# create a restart file for the next next cycle
sleep $(( TASK_RUN_TIME_SECONDS / 3 ))
touch $CYLC_TMPDIR/${TASK_NAME}-${NEXT_NEXT_CYCLE}.restart
cylc task-message --next-restart-completed

# create storm surge forecast output
sleep $(( TASK_RUN_TIME_SECONDS / 3 ))
touch $CYLC_TMPDIR/storm-surge-${CYCLE_TIME}.nc
cylc task-message "storm surge fields ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
