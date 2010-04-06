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
# Task F: postprocess the storm surge model.

# UNLIKE THE OTHER TASKS IN THE USERGUIDE EXAMPLE SYSTEM, THIS ONE IS
# NOT CYLC-AWARE, SO IT HAS TO BE RUN USING THE CYLC TASK WRAPPING
# MECHANISM. 

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# check prerequisites
SUBSYS_CYLC_TMPDIR=/tmp/$USER/userguide
PRE=$SUBSYS_CYLC_TMPDIR/storm-surge-${ANALYSIS_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE
    echo "file not found: $PRE"
    exit 1
fi

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

touch $CYLC_TMPDIR/storm-surge-products-${ANALYSIS_TIME}.nc
