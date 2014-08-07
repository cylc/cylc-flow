#!/bin/bash

# Task Event Hook script to clean up if the fam family fails, by
# removing the failed task from the suite. You probably don't want to do
# this in practice (failed tasks should generally be removed manually
# after determining the reason for the failure); but this shows that
# hook scripts can intervene in the running of their own suite.

# inputs supplied by cylc
EVENT=$1; SUITE=$2; TASK=$3; MSG=$4

echo "(HOOK SCRIPT: waiting 10 seconds)"
sleep 10 # (time to observe failed task in the suite monitor).

# check that the task has in fact failed
NAME=${TASK%\%*}
TIME=${TASK#*%}
RES=$( cylc dump $SUITE | grep $NAME | grep $TIME )
STATE=$( echo $RES | awk '{print $3}' | sed -e 's/,//' )
if [[ $STATE != failed ]]; then
    echo "HOOK SCRIPT: ERROR: $TASK is not failed: $STATE"
    exit 1
else
    echo "HOOK SCRIPT: $TASK is failed (as expected)."
fi

echo "REMOVING FAILED TASK: $TASK"
cylc control remove --force $CYLC_SUITE_REG_NAME $TASK
