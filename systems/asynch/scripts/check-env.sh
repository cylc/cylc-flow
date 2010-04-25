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

if [[ -z $CYLC_TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$CYLC_TMPDIR is not defined"
    cylc message --failed
    exit 1
fi
