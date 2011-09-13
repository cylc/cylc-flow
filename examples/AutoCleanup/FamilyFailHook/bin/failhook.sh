#!/bin/bash

# Hook script to clean up if the fammo family fails, by removing failed
# members from the suite. You probably don't want to do this in practice
# (failed tasks should be removed manually, after determining the reason
# for the failure); but this shows that hook scripts can intervene in
# the running of their own suite.

# Check inputs
EVENT=$1; SUITE=$2; TASK=$3; MSG=$4
if [[ $TASK != m_* ]]; then
    echo "ERROR: failure hook script called for the wrong task"
    exit 1
fi

CTIME=${TASK#*%}

sleep 10 # (time to observe the failed tasks in the suite monitor).
# Determine which family member(s) failed, if any
FAILED_TASKS=$(cylc dump $SUITE | grep $CTIME | grep failed | sed -e 's/,.*$//')

found_failed_member=false
echo "FAILED TASKS:"
for T in $FAILED_TASKS; do
    echo -n "   $T ..."
    if [[ $T == m_* ]]; then
        found_failed_member=true
        echo "REMOVING family member"
        cylc control remove --force $CYLC_SUITE_REG_NAME ${T}%$CTIME
    else
        echo "NOT REMOVING (not family member)"
    fi
done
