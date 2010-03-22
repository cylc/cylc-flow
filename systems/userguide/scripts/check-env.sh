#!/bin/bash

# CHECK ENVIRONMENT

if [[ -z $REAL_TIME_ACCEL ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$REAL_TIME_ACCEL is not defined"
    cylc message --failed
    exit 1
fi

if [[ -z $TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$TMPDIR is not defined"
    cylc message --failed
    exit 1
fi

if [[ ! -z FAIL_TASK ]]; then
    # user has ordered a particular task to fail
    if [[ $FAIL_TASK == ${TASK_NAME}%${CYCLE_TIME} ]]; then
        if [[ -f $TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already ]]; then
            cylc message -p WARNING "FAIL_TASK has been used already!"
        else
            # FAILURE MESSAGE
            touch $TMPDIR/${TASK_NAME}%${CYCLE_TIME}.failed_already 
            cylc message -p CRITICAL "ABORT ordered via \$FAIL_TASK"
            cylc message --failed
            exit 1
        fi
    fi
fi
