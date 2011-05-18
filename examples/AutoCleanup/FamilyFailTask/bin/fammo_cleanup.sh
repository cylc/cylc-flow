#!/bin/bash

# This script cleans up if the fammo task family fails

echo "Hello from ${TASK_ID} preparing to clean up family fammo"

# Sleep for 10 seconds so there's time for failed tasks to be seen
sleep 10

# determine which family member(s) failed
FAILED_TASKS=$(cylc dump $CYLC_SUITE | grep failed | sed -e 's/,.*$//')

# remove failed members (use --force for non-interactive!)
found_failed_member=false
for T in $FAILED_TASKS; do
    if [[ $T == m_* ]]; then
        found_failed_member=true
        echo cylc control remove --force $CYLC_SUITE ${T}%$CYCLE_TIME
        cylc control remove --force $CYLC_SUITE ${T}%$CYCLE_TIME
    fi
done
if $found_failed_member; then
    # remove the family itself (use --force for non-interactive!)
    echo cylc control remove --force $CYLC_SUITE fammo$CYCLE_TIME
    cylc control remove --force $CYLC_SUITE $fammo$CYCLE_TIME
fi
