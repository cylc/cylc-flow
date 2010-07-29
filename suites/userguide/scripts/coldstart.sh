#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM cold start task IMPLEMENTATION.

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# check environment
check-env.sh || exit 1

# EXECUTE THE TASK ...
sleep $TASK_RUN_TIME_SECONDS

touch $CYLC_TMPDIR/TaskA-${CYCLE_TIME}.restart
cylc task-message "TaskA restart files ready for $CYCLE_TIME"
touch $CYLC_TMPDIR/TaskB-${CYCLE_TIME}.restart
cylc task-message "TaskB restart files ready for $CYCLE_TIME"
touch $CYLC_TMPDIR/TaskC-${CYCLE_TIME}.restart
cylc task-message "TaskC restart files ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
