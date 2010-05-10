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
    cylc message -p CRITICAL "\$REAL_TIME_ACCEL is not defined"
    cylc message --failed
    exit 1
fi

if [[ -z $CYLC_TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$CYLC_TMPDIR is not defined"
    cylc message --failed
    exit 1
fi

if [[ ! -z FAIL_TASK ]]; then
    # user has ordered a particular task to fail
    if [[ $FAIL_TASK == ${TASK_NAME}%${CYCLE_TIME} ]]; then
        if [[ -f $CYLC_TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already ]]; then
            cylc message -p WARNING "FAIL_TASK has been used already!"
        else
            # FAILURE MESSAGE
            touch $CYLC_TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already 
            cylc message -p CRITICAL "ABORT ordered via \$FAIL_TASK"
            cylc message --failed
            exit 1
        fi
    fi
fi
