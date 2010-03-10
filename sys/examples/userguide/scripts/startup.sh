#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# oneoff startup task to clean out the system work space.

# run length 10 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

mkdir -p $TMPDIR || \
{
    cylc message -p CRITICAL "failed to create $TMPDIR"
    cylc message --failed
    exit 1
}

# EXECUTE THE TASK ...
sleep $SLEEP 

echo "CLEANING $TMPDIR"
rm -rf $TMPDIR/* || \
{
    cylc message -p CRITICAL "failed to clean out $TMPDIR"
    cylc message --failed
    exit 1
}

# SUCCESS MESSAGE
cylc message --succeeded
