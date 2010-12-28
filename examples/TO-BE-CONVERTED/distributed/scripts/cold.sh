#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# cylc example suite, task cold
# one off cold start task
# generates restart files for forecast
# no prerequisites

# run length 10 minutes

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

cylc task-started || exit 1

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

RUNDIR=$CYLC_REMOTE_TMPDIR/running/$CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc task-message "forecast restart files ready for $CYCLE_TIME"

cylc task-finished
