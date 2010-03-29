#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE SCS-DEMO SYSTEM. 
# oneoff startup task to inform the user that this system can only be
# run in dummy mode!

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# WARN AND ABORT
cylc message -p CRITICAL "THIS EXAMPLE SYSTEM HAS NO REAL MODE IMPLEMENTATION"
cylc message -p CRITICAL "YOU CAN RUN IT ONLY IN DUMMY MODE. GOODBYE. REALLY."
cylc message --failed
exit 1
