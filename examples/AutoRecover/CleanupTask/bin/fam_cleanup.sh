#!/bin/bash
set -e

# Task script to clean up if the fammo family fails, by removing failed
# members from the suite. You probably don't want to do this in practice
# (failed tasks should be removed manually, after determining the reason
# for the failure); but this shows how task scripts can intervene in
# their suite.

sleep 10 # (time to observe the failed tasks in the suite monitor).

# Determine which family member(s) failed, if any
FAILED_TASKS=$(cylc dump $CYLC_SUITE_REG_NAME | grep $CYLC_TASK_CYCLE_TIME | grep failed | sed -e 's/,.*$//')

found_failed_member=false
echo "FAILED TASKS:"
for T in $FAILED_TASKS; do
    echo -n "   $T ..."
    if [[ $T == m_* ]]; then
        found_failed_member=true
        echo "REMOVING family member"
        cylc control remove --force $CYLC_SUITE_REG_NAME ${T}.$CYLC_TASK_CYCLE_TIME
    else
        echo "NOT REMOVING (not family member)"
    fi
done
