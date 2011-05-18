#!/bin/bash

# This is a cylc task event hook script
EVENT=$1; FTASK=$2; CTIME=$3; MSG=$4

# check inputs
echo "FAILURE HOOK SCRIPT FOR FAMILY 'fammo'"
#echo "ARGUMENTS: ${EVENT}, ${FTASK}, ${CTIME},  \"$MSG\""
if [[ $FTASK != fammo ]]; then
    echo "ERROR: failure hook script called for the wrong task"
    exit 1
fi

# Sleep for 10 seconds so there's time for failed tasks to be seen
sleep 10

# determine which family member(s) failed
FAILED_TASKS=$(cylc dump $CYLC_SUITE | grep failed | sed -e 's/,.*$//')

# remove failed members (use --force for non-interactive!)
for T in $FAILED_TASKS; do
    if [[ $T == m_* ]]; then
        # detected a failed family member
        echo cylc control remove --force $CYLC_SUITE ${T}%$CTIME
        cylc control remove --force $CYLC_SUITE ${T}%$CTIME
    fi
done
# remove the family itself (use --force for non-interactive!)
echo cylc control remove --force $CYLC_SUITE ${FTASK}%$CTIME
cylc control remove --force $CYLC_SUITE ${FTASK}%$CTIME
