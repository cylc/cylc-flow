#!/bin/bash

set -e

# Shutdown, wait, restart. Use to reload suite changes without having to 
# wait around for currently running tasks to finish prior to a manual
# restart. Be aware that suite stdout and stderr will be reattached to
# this process on the restart.

# AWAITING INCORPORATION INTO THE MAIN CYLC INTERFACE, IF USEFUL.

SUITE=$1

cylc shutdown -f $SUITE

echo "Waiting for $SUITE to shut down"
echo -n "."

while true; do
    STILL_RUNNING=false
    cylc ping $SUITE && STILL_RUNNING=true
    ! $STILL_RUNNING && break
    sleep 1
    echo -n "."
done
echo

echo "Restarting $SUITE"
cylc restart $SUITE


