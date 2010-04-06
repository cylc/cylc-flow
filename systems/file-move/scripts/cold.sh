#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# cylc file-move example system, oneoff coldstart task
# generates restart files for forecast
# no prerequisites

# run length 10 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# check environment
check-env.sh || exit 1

sleep $(( 10 * 60 / REAL_TIME_ACCEL )) 

RUNDIR=$CYLC_TMPDIR/forecast/running/$CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc message "forecast restart files ready for $CYCLE_TIME"

cylc message --succeeded
