#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# cylc example system, task forecast
# depends on task ext and its own restart file.

# run length 10 minutes, one restart file

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# check environment
check-env.sh || exit 1

# check prerequistes
ONE=$CYLC_TMPDIR/ext/output/$CYCLE_TIME/extdata
TWO=$CYLC_TMPDIR/$TASK_NAME/running/$CYCLE_TIME/restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, forecast: $MSG"
        cylc message -p CRITICAL $MSG
        cylc message --failed
        exit 1
    }
done

sleep $(( 10 * 60 / REAL_TIME_ACCEL ))

RUNDIR=$CYLC_TMPDIR/$TASK_NAME/running/$NEXT_CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc message --next-restart-completed

OUTDIR=$CYLC_TMPDIR/$TASK_NAME/output/$CYCLE_TIME
mkdir -p $OUTDIR
touch $OUTDIR/forecast.nc
cylc message "forecast output ready for $CYCLE_TIME"

cylc message --succeeded
