#!/bin/bash

# cylc example suite, task startup
# one off initial task to clean the example suite working directory
# no prerequisites

# run length 10 minutes

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

cylc task-started || exit 1

if [[ -z $CYLC_TMPDIR ]]; then
    cylc task-failed "\$CYLC_TMPDIR must be defined in suite_config.py for this suite"
    exit 1
fi

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

mkdir -p $CYLC_TMPDIR || {
    MSG="failed to make $CYLC_TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc task-failed $MSG
    exit 1
}

sleep $SLEEP 

echo "CLEANING $CYLC_TMPDIR"
rm -rf $CYLC_TMPDIR/* || {
    MSG="failed to clean $CYLC_TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc task-failed $MSG
    exit 1
}

cylc task-finished
