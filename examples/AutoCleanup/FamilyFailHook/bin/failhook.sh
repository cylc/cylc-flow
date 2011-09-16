#!/bin/bash

# Hook script to clean up if the fammo family fails, by removing the failed
# task from the suite. You probably don't want to do this in practice
# (failed tasks should be removed manually, after determining the reason
# for the failure); but this shows that hook scripts can intervene in
# the running of their own suite.

# Check inputs
EVENT=$1; SUITE=$2; TASK=$3; MSG=$4
if [[ $TASK != m_* ]]; then
    echo "ERROR: failure hook script called for the wrong task"
    exit 1
fi

sleep 10 # (time to observe the failed tasks in the suite monitor).

echo "REMOVING FAILED TASK: $TASK"
cylc control remove --force $CYLC_SUITE_REG_NAME $TASK
