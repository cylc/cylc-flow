#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SUITE,
# Task to get real time obs data for the atmospheric model.

# Run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

# "find" the external data and report it available
touch $CYLC_TMPDIR/obs-${CYCLE_TIME}.nc
cylc task-message "obs data ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
