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

echo "Hello from $TASK_ID"
echo "Checking Environment ..."

echo -n " 1 ... "
if [[ -z $REAL_TIME_ACCEL ]]; then
    # FAILURE MESSAGE
    cylc task-failed "\$REAL_TIME_ACCEL is not defined"
    exit 1
fi
echo "ok"

echo -n " 2 ... "
if [[ -z $CYLC_TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc task-failed "\$CYLC_TMPDIR is not defined"
    exit 1
fi
echo "ok"

MSG="Environment checks out OK"
cylc task-message $MSG

if [[ ! -z FAIL_TASK ]]; then
    # user has ordered a particular task to fail
    if [[ $FAIL_TASK == ${TASK_NAME}%${CYCLE_TIME} ]]; then
        if [[ -f $CYLC_TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already ]]; then
            cylc task-message -p WARNING "FAIL_TASK has been used already!"
        else
            # FAILURE MESSAGE
            touch $CYLC_TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already 
            MSG="ABORTING: requested via \$FAIL_TASK in system config"
            cylc task-failed $MSG
            exit 1
        fi
    fi
fi
