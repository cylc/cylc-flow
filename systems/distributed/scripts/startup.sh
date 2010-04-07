#!/bin/bash

# cylc example system, task startup
# one off initial task to clean the example system working directory
# no prerequisites

# run length 10 minutes

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

if [[ -z $CYLC_TMPDIR ]]; then
    cylc message -p CRITICAL "\$CYLC_TMPDIR must be defined in system_config.py for this system"
    cylc message --failed
    exit 1
fi

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

mkdir -p $CYLC_TMPDIR || {
    MSG="failed to make $CYLC_TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc message -p CRITICAL $MSG
    cylc message --failed
    exit 1
}

sleep $SLEEP 

echo "CLEANING $CYLC_TMPDIR"
rm -rf $CYLC_TMPDIR/* || {
    MSG="failed to clean $CYLC_TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc message -p CRITICAL $MSG
    cylc message --failed
    exit 1
}

cylc message --succeeded
