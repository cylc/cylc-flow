#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC CONDITIONAL EXAMPLE SUITE
# oneoff startup task to inform the user that this suite can only be
# run in dummy mode!

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started

# WARN AND ABORT
cylc task-message -p CRITICAL "THIS EXAMPLE SUITE HAS NO REAL MODE IMPLEMENTATION"
cylc task-message -p CRITICAL "YOU CAN RUN IT ONLY IN DUMMY MODE. GOODBYE. REALLY."
cylc task-failed
exit 1
