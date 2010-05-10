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

# run time scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# no prerequisites to check

CYCLE=$CYCLE_TIME

while true; do
    sleep 10
    cylc message "external data ready for $CYCLE"
    cylc message "crap ready for ${CYCLE}, ass hole"
    CYCLE=$( cylc-time -a 6 $CYCLE )
done

# SUCCESS MESSAGE (NEVER REACHED!)
cylc message --succeeded
