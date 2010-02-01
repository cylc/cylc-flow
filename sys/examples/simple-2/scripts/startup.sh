#!/bin/bash

# cylc example system, task startup
# one off initial task to clean the example system working directory
# no prerequisites

# run length 10 minutes

cylc-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

mkdir -p $TMPDIR || {
    MSG="failed to make $TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc-message -p CRITICAL $MSG
    cylc-message -p CRITICAL failed
    exit 1
}

sleep $SLEEP 

echo "CLEANING $TMPDIR"
rm -rf $TMPDIR/* || {
    MSG="failed to clean $TMPDIR"
    echo "ERROR, startup: $MSG"
    cylc-message -p CRITICAL $MSG
    cylc-message -p CRITICAL failed
    exit 1
}

cylc-message finished
