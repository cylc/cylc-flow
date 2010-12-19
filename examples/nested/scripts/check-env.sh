#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CHECK ENVIRONMENT

if [[ -z $REAL_TIME_ACCEL ]]; then
    # FAILURE MESSAGE
    cylc task-failed "\$REAL_TIME_ACCEL is not defined"
    exit 1
fi

if [[ -z $CYLC_TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc task-failed "\$CYLC_TMPDIR is not defined"
    exit 1
fi
