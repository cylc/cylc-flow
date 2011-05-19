#!/bin/bash
set -e

# This task script cleans up if the fammo family fails: it removes
# failed family members, and the failed family itself, from the suite.

sleep 10 # (time to observe the failed tasks in the suite monitor).

# Determine which family member(s) failed, if any
FAILED_TASKS=$(cylc dump $CYLC_SUITE | grep $CYCLE_TIME | grep failed | sed -e 's/,.*$//')

found_failed_member=false
echo "FAILED TASKS:"
for T in $FAILED_TASKS; do
    echo -n "   $T ..."
    if [[ $T == m_* ]]; then
        found_failed_member=true
        echo "REMOVING (family member)"
        cylc control remove --force $CYLC_SUITE ${T}%$CYCLE_TIME
    else
        echo "NOT REMOVING (not family member)"
    fi
done
if $found_failed_member; then
    echo "REMOVING (family)"
    cylc control remove --force $CYLC_SUITE fammo%$CYCLE_TIME
fi
